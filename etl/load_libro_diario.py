#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Carga libros diarios E&V a Neon/Postgres.

Uso:
  python load_libro_diario.py diarioext.xls
  python load_libro_diario.py diarioext.xls --empresa "E&V Calera de Tango"
  python load_libro_diario.py diarioext.xls --dry-run
  python load_libro_diario.py diarioext.xls --replace

Regla:
  saldo_ml = haber_ml - debe_ml
  cuentas 4/5/6 = EERR; resto = Balance
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


EMPRESAS = [
    "E&V Algarrobo",
    "E&V Calera de Tango",
    "E&V Chile",
    "E&V Comercial",
    "E&V Lo Barnechea",
    "E&V Ñuñoa",
    "E&V Rancagua",
    "E&V Vitacura",
]

EXPECTED_NO_HEADER = [
    "fecha",
    "tipo_comprobante",
    "numero_comprobante",
    "secuencia",
    "glosa",
    "cuenta_contable",
    "cuenta_nombre",
    "ignorar",
    "debe_ml",
    "haber_ml",
]

COLUMN_ALIASES = {
    "fecha": ["fecha", "fec", "date"],
    "tipo_comprobante": ["tipo", "tipo comp.", "tipo comp", "tipo comprobante", "tipo_comprobante"],
    "numero_comprobante": ["nº comp.", "n° comp.", "nro comp.", "num comp.", "numero comprobante", "numero_comprobante", "n comp"],
    "secuencia": ["sec", "secuencia"],
    "glosa": ["glosa", "detalle", "descripcion", "descripción"],
    "cuenta_contable": ["cuenta", "cuenta contable", "cuenta_contable", "codigo cuenta", "código cuenta"],
    "cuenta_nombre": ["glosa cuenta", "nombre cuenta", "cuenta nombre", "cuenta_nombre"],
    "debe_ml": ["debe", "debe m/l", "debe ml", "debe_ml"],
    "haber_ml": ["haber", "haber m/l", "haber ml", "haber_ml"],
}


def sanitize_schema(schema: str) -> str:
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", schema):
        raise ValueError(f"Schema inválido: {schema}")
    return schema


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_col_name(value: Any) -> str:
    text = str(value).strip().lower()
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text)
    return text


def looks_like_header(first_row: pd.Series) -> bool:
    values = [normalize_col_name(v) for v in first_row.tolist()]
    joined = " | ".join(values)
    hits = 0
    for aliases in COLUMN_ALIASES.values():
        if any(alias in values or alias in joined for alias in aliases):
            hits += 1
    return hits >= 3


def normalize_number(value: Any) -> float:
    if pd.isna(value) or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return 0.0

    text = text.replace("$", "").replace("CLP", "").replace(" ", "")

    # formato chileno: 1.234.567,89
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    # formato chileno entero: 1.234.567
    elif "." in text and re.match(r"^-?\d{1,3}(\.\d{3})+$", text):
        text = text.replace(".", "")
    elif "," in text:
        text = text.replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return 0.0


def extract_account_code(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    # 51.01.01 - Nombre => 510101
    m = re.match(r"^\s*([0-9][0-9\.\- ]*)", text)
    raw = m.group(1) if m else text
    return re.sub(r"\D", "", raw)


def extract_account_name(cuenta_contable: Any, cuenta_nombre: Any) -> str:
    if cuenta_nombre is not None and not pd.isna(cuenta_nombre) and str(cuenta_nombre).strip():
        return str(cuenta_nombre).strip()
    if cuenta_contable is None or pd.isna(cuenta_contable):
        return ""
    text = str(cuenta_contable).strip()
    parts = re.split(r"\s+-\s+", text, maxsplit=1)
    if len(parts) == 2:
        return parts[1].strip()
    return text


def choose_empresa() -> str:
    print("\n¿Qué empresa estás cargando?")
    for i, emp in enumerate(EMPRESAS, 1):
        print(f"{i}. {emp}")
    while True:
        raw = input("Selecciona número de empresa: ").strip()
        try:
            idx = int(raw)
            if 1 <= idx <= len(EMPRESAS):
                return EMPRESAS[idx - 1]
        except ValueError:
            pass
        print("Opción inválida. Intenta nuevamente.")


def read_excel_any(path: Path) -> tuple[pd.DataFrame, bool]:
    raw = pd.read_excel(path, header=None, dtype=object)
    raw = raw.dropna(how="all")
    if raw.empty:
        raise ValueError("El archivo no tiene filas útiles.")

    has_header = looks_like_header(raw.iloc[0])

    if has_header:
        header = [normalize_col_name(x) for x in raw.iloc[0].tolist()]
        df = raw.iloc[1:].copy()
        df.columns = header

        rename = {}
        for canonical, aliases in COLUMN_ALIASES.items():
            for col in df.columns:
                if col in aliases:
                    rename[col] = canonical
                    break
        df = df.rename(columns=rename)
        # Evita errores cuando el Excel trae columnas duplicadas
#       o cuando más de una columna se renombra al mismo nombre.
        df = df.loc[:, ~df.columns.duplicated()].copy()
    else:
        df = raw.copy()
        cols = EXPECTED_NO_HEADER + [f"extra_{i}" for i in range(max(0, df.shape[1] - len(EXPECTED_NO_HEADER)))]
        df.columns = cols[: df.shape[1]]

    return df, has_header


def normalize_libro(path: Path, empresa: str) -> tuple[pd.DataFrame, bool, str]:
    df, has_header = read_excel_any(path)
    sha = file_sha256(path)

    required = ["fecha", "cuenta_contable", "debe_ml", "haber_ml"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas mínimas: {missing}. Columnas detectadas: {list(df.columns)}")

    # Ensure optional columns
    for col in ["tipo_comprobante", "numero_comprobante", "secuencia", "glosa", "cuenta_nombre"]:
        if col not in df.columns:
            df[col] = ""

    out = pd.DataFrame()
    out["empresa"] = empresa
    out["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").dt.date
    out["periodo"] = pd.to_datetime(df["fecha"], errors="coerce").dt.strftime("%Y-%m")
    out["tipo_comprobante"] = df["tipo_comprobante"].fillna("").astype(str).str.strip()
    out["numero_comprobante"] = df["numero_comprobante"].fillna("").astype(str).str.strip()
    out["secuencia"] = df["secuencia"].fillna("").astype(str).str.strip()
    out["glosa"] = df["glosa"].fillna("").astype(str).str.strip()
    out["cuenta_contable"] = df["cuenta_contable"].fillna("").astype(str).str.strip()
    out["cuenta_codigo"] = df["cuenta_contable"].apply(extract_account_code)
    out["cuenta_nombre"] = [
        extract_account_name(c, n) for c, n in zip(df["cuenta_contable"], df["cuenta_nombre"])
    ]
    out["debe_ml"] = df["debe_ml"].apply(normalize_number)
    out["haber_ml"] = df["haber_ml"].apply(normalize_number)
    out["saldo_ml"] = out["haber_ml"] - out["debe_ml"]
    out["cuenta_eerr"] = out["cuenta_codigo"].str[0].isin(["4", "5", "6"]).map({True: "EERR", False: "BALANCE"})
    out["line_number"] = range(1, len(out) + 1)
    out["file_sha256"] = sha

    out = out.dropna(subset=["fecha"])
    out = out[out["cuenta_codigo"] != ""]
    out = out[(out["debe_ml"] != 0) | (out["haber_ml"] != 0)].copy()

    return out, has_header, sha


def print_summary(df: pd.DataFrame, path: Path, empresa: str, has_header: bool, sha: str) -> None:
    print("\nResumen de carga")
    print("-" * 80)
    print(f"Archivo:        {path}")
    print(f"SHA256:         {sha}")
    print(f"Headers:        {'sí' if has_header else 'no'}")
    print(f"Empresa:        {empresa}")
    print(f"Filas válidas:  {len(df):,}")
    print(f"Fecha mínima:   {df['fecha'].min()}")
    print(f"Fecha máxima:   {df['fecha'].max()}")
    print(f"Debe M/L:       {df['debe_ml'].sum():,.0f}")
    print(f"Haber M/L:      {df['haber_ml'].sum():,.0f}")
    print(f"Saldo M/L:      {df['saldo_ml'].sum():,.0f}")
    print(f"Filas EERR:     {(df['cuenta_eerr'] == 'EERR').sum():,}")
    print(f"Filas Balance:  {(df['cuenta_eerr'] == 'BALANCE').sum():,}")

    monthly = (
        df.groupby(["periodo", "cuenta_eerr"], as_index=False)
        .agg(filas=("cuenta_codigo", "size"), debe_ml=("debe_ml", "sum"), haber_ml=("haber_ml", "sum"), saldo_ml=("saldo_ml", "sum"))
        .sort_values(["periodo", "cuenta_eerr"])
    )
    print("\nResumen mensual")
    print(monthly.to_string(index=False))

    eerr = (
        df[df["cuenta_eerr"] == "EERR"]
        .groupby(["cuenta_codigo", "cuenta_nombre"], as_index=False)
        .agg(saldo_ml=("saldo_ml", "sum"), debe_ml=("debe_ml", "sum"), haber_ml=("haber_ml", "sum"))
    )
    if not eerr.empty:
        eerr["abs_saldo"] = eerr["saldo_ml"].abs()
        eerr = eerr.sort_values("abs_saldo", ascending=False).head(10)
        eerr["cuenta_contable"] = eerr["cuenta_codigo"] + " - " + eerr["cuenta_nombre"]
        print("\nTop 10 cuentas EERR por monto absoluto")
        print(eerr[["cuenta_contable", "saldo_ml", "debe_ml", "haber_ml"]].to_string(index=False))


def ensure_schema_and_tables(conn: psycopg.Connection, schema: str) -> None:
    schema = sanitize_schema(schema)
    with conn.cursor() as cur:
        cur.execute(f"create schema if not exists {schema};")

        cur.execute(f"""
        create table if not exists {schema}.empresas (
            id bigserial primary key,
            nombre text not null unique,
            activa boolean not null default true,
            created_at timestamptz not null default now()
        );
        """)

        cur.execute(f"""
        create table if not exists {schema}.cargas_libro_diario (
            id bigserial primary key,
            empresa text not null,
            archivo_nombre text not null,
            file_sha256 text not null,
            filas integer not null,
            fecha_min date,
            fecha_max date,
            debe_ml numeric(18,2) not null default 0,
            haber_ml numeric(18,2) not null default 0,
            saldo_ml numeric(18,2) not null default 0,
            metadata jsonb,
            created_at timestamptz not null default now()
        );
        """)

        cur.execute(f"""
        create table if not exists {schema}.fact_libro_diario (
            id bigserial primary key,
            carga_id bigint references {schema}.cargas_libro_diario(id) on delete cascade,
            empresa text not null,
            periodo text not null,
            fecha date not null,
            tipo_comprobante text,
            numero_comprobante text,
            secuencia text,
            glosa text,
            cuenta_codigo text not null,
            cuenta_nombre text,
            cuenta_contable text,
            debe_ml numeric(18,2) not null default 0,
            haber_ml numeric(18,2) not null default 0,
            saldo_ml numeric(18,2) not null default 0,
            cuenta_eerr text not null,
            line_number integer,
            file_sha256 text,
            created_at timestamptz not null default now()
        );
        """)

        # Migrations for prior versions
        cur.execute(f"alter table {schema}.fact_libro_diario add column if not exists saldo_ml numeric(18,2) not null default 0;")
        cur.execute(f"update {schema}.fact_libro_diario set saldo_ml = coalesce(haber_ml,0) - coalesce(debe_ml,0) where saldo_ml is null or saldo_ml = 0;")

        cur.execute(f"create index if not exists idx_fact_libro_empresa_periodo on {schema}.fact_libro_diario (empresa, periodo);")
        cur.execute(f"create index if not exists idx_fact_libro_cuenta on {schema}.fact_libro_diario (cuenta_codigo);")
        cur.execute(f"create index if not exists idx_fact_libro_carga on {schema}.fact_libro_diario (carga_id);")

        cur.execute(f"""
        create or replace view {schema}.v_resumen_cargas as
        select
            id as carga_id,
            empresa,
            archivo_nombre,
            file_sha256,
            filas,
            fecha_min,
            fecha_max,
            debe_ml,
            haber_ml,
            saldo_ml,
            created_at
        from {schema}.cargas_libro_diario;
        """)

        cur.execute(f"""
        create or replace view {schema}.v_eerr_mensual_cuenta as
        select
            empresa,
            periodo,
            cuenta_codigo,
            cuenta_nombre,
            sum(debe_ml) as debe_ml,
            sum(haber_ml) as haber_ml,
            sum(saldo_ml) as saldo_ml,
            count(*) as movimientos
        from {schema}.fact_libro_diario
        where cuenta_eerr = 'EERR'
        group by empresa, periodo, cuenta_codigo, cuenta_nombre;
        """)

        for emp in EMPRESAS:
            cur.execute(f"insert into {schema}.empresas(nombre) values (%s) on conflict (nombre) do nothing;", (emp,))


def insert_libro(conn: psycopg.Connection, df: pd.DataFrame, schema: str, path: Path, sha: str, replace: bool) -> int:
    schema = sanitize_schema(schema)
    empresa = str(df["empresa"].iloc[0])
    with conn.cursor(row_factory=dict_row) as cur:
        if replace:
            cur.execute(f"""
                delete from {schema}.cargas_libro_diario
                where empresa = %s and file_sha256 = %s;
            """, (empresa, sha))

        cur.execute(f"""
            insert into {schema}.cargas_libro_diario (
                empresa, archivo_nombre, file_sha256, filas, fecha_min, fecha_max,
                debe_ml, haber_ml, saldo_ml, metadata
            )
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            returning id;
        """, (
            empresa,
            path.name,
            sha,
            int(len(df)),
            df["fecha"].min(),
            df["fecha"].max(),
            float(df["debe_ml"].sum()),
            float(df["haber_ml"].sum()),
            float(df["saldo_ml"].sum()),
            Jsonb({"source": "load_libro_diario.py"}),
        ))
        carga_id = int(cur.fetchone()["id"])

        rows = []
        for r in df.to_dict(orient="records"):
            rows.append((
                carga_id,
                r["empresa"],
                r["periodo"],
                r["fecha"],
                r["tipo_comprobante"],
                r["numero_comprobante"],
                r["secuencia"],
                r["glosa"],
                r["cuenta_codigo"],
                r["cuenta_nombre"],
                r["cuenta_contable"],
                float(r["debe_ml"]),
                float(r["haber_ml"]),
                float(r["saldo_ml"]),
                r["cuenta_eerr"],
                int(r["line_number"]),
                r["file_sha256"],
            ))

        cur.executemany(f"""
            insert into {schema}.fact_libro_diario (
                carga_id, empresa, periodo, fecha, tipo_comprobante, numero_comprobante,
                secuencia, glosa, cuenta_codigo, cuenta_nombre, cuenta_contable,
                debe_ml, haber_ml, saldo_ml, cuenta_eerr, line_number, file_sha256
            )
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
        """, rows)

    return carga_id


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("archivo", help="Archivo .xls/.xlsx de libro diario")
    parser.add_argument("--empresa", choices=EMPRESAS)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--schema", default=os.getenv("FINANZAS_SCHEMA", "finanzas"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true", help="Si ya existe una carga con mismo empresa+hash, la reemplaza")
    parser.add_argument("--export-csv")
    args = parser.parse_args()

    path = Path(args.archivo)
    if not path.exists():
        print(f"No existe el archivo: {path}", file=sys.stderr)
        return 1

    empresa = args.empresa or choose_empresa()
    df, has_header, sha = normalize_libro(path, empresa)
    print_summary(df, path, empresa, has_header, sha)

    if args.export_csv:
        df.to_csv(args.export_csv, index=False, encoding="utf-8-sig")
        print(f"\nCSV exportado: {args.export_csv}")

    if args.dry_run:
        print("\nDry run: no se cargó a Postgres.")
        return 0

    if not args.database_url:
        print("\nFalta DATABASE_URL. Agrégalo a .env o usa --database-url.", file=sys.stderr)
        return 1

    schema = sanitize_schema(args.schema)
    with psycopg.connect(args.database_url) as conn:
        ensure_schema_and_tables(conn, schema)
        carga_id = insert_libro(conn, df, schema, path, sha, args.replace)
        conn.commit()

    print(f"\nCarga completada en Postgres. carga_id={carga_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
