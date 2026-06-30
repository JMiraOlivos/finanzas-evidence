#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Carga libros diarios E&V a Neon/Postgres.

Uso:
  python load_libro_diario.py diarioext.xls --replace --reset-schema
  python load_libro_diario.py diarioext.xls --empresa "E&V Calera de Tango" --replace

Para archivos sin headers:
- El script detecta automáticamente columna de fecha, cuenta contable, debe y haber.
- También acepta override manual con columnas 1-based:
  python load_libro_diario.py diarioext.xls --fecha-col 1 --cuenta-col 6 --debe-col 9 --haber-col 10

Reglas:
- saldo_ml = haber_ml - debe_ml
- cuentas que comienzan con 4, 5 o 6 => EERR
- resto => BALANCE
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

COLUMN_ALIASES = {
    "fecha": ["fecha", "fec", "date"],
    "tipo_comprobante": ["tipo", "tipo comp.", "tipo comp", "tipo comprobante", "tipo_comprobante"],
    "numero_comprobante": ["nº comp.", "n° comp.", "nro comp.", "num comp.", "numero comprobante", "número comprobante", "numero_comprobante", "n comp"],
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

    # Manejo de números negativos entre paréntesis.
    neg = False
    if text.startswith("(") and text.endswith(")"):
        neg = True
        text = text[1:-1]

    # Formato chileno: 1.234.567,89
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    # Formato chileno entero: 1.234.567
    elif "." in text and re.match(r"^-?\d{1,3}(\.\d{3})+$", text):
        text = text.replace(".", "")
    elif "," in text:
        text = text.replace(",", ".")

    try:
        num = float(text)
        return -num if neg else num
    except ValueError:
        return 0.0


def extract_account_code(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    m = re.match(r"^\s*([0-9][0-9\.\- ]*)", text)
    raw = m.group(1) if m else text
    return re.sub(r"\D", "", raw)


def extract_account_name(cuenta_contable: Any, cuenta_nombre: Any) -> str:
    if cuenta_nombre is not None and not pd.isna(cuenta_nombre):
        text = str(cuenta_nombre).strip()
        if text:
            return text

    if cuenta_contable is None or pd.isna(cuenta_contable):
        return ""

    text = str(cuenta_contable).strip()
    parts = re.split(r"\s+-\s+", text, maxsplit=1)
    if len(parts) == 2:
        return parts[1].strip()

    return text


def get_col(df: pd.DataFrame, col: str, default: Any = "") -> pd.Series:
    if col not in df.columns:
        return pd.Series([default] * len(df), index=df.index)
    value = df[col]
    if isinstance(value, pd.DataFrame):
        return value.iloc[:, 0]
    return value


def choose_empresa() -> str:
    print("\n¿Qué empresa/oficina estás cargando?")
    for i, emp in enumerate(EMPRESAS, 1):
        print(f"{i}. {emp}")

    while True:
        raw = input("Selecciona número: ").strip()
        try:
            idx = int(raw)
            if 1 <= idx <= len(EMPRESAS):
                return EMPRESAS[idx - 1]
        except ValueError:
            pass
        print("Opción inválida. Intenta nuevamente.")


def score_date_series(s: pd.Series) -> float:
    """
    Score estricto para detectar columna de fecha.

    Evita falsos positivos como columnas numéricas 101, 102, etc.,
    que pandas puede convertir a fechas tipo 1970-01-01.
    """
    non_null = s.dropna()
    if non_null.empty:
        return 0.0

    # Bonus fuerte si los valores parecen fechas escritas con separadores.
    as_text = non_null.astype(str).str.strip()
    text_date_like = as_text.str.match(
        r"^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}$|^\d{4}[-/]\d{1,2}[-/]\d{1,2}$"
    )
    text_ratio = float(text_date_like.mean())

    parsed = pd.to_datetime(non_null, errors="coerce", dayfirst=True)
    valid = parsed.notna()

    if valid.sum() == 0:
        return 0.0

    years = parsed[valid].dt.year
    plausible_year = years.between(1990, 2100)
    plausible_ratio = float(plausible_year.mean())

    # Penaliza columnas puramente numéricas de bajo valor, típicas de número de comprobante.
    numeric_like = as_text.str.match(r"^\d+(\.0)?$")
    low_numeric_ratio = float((numeric_like & as_text.str.replace(".0", "", regex=False).str.len().le(4)).mean())

    return (text_ratio * 0.75) + (plausible_ratio * 0.35) - (low_numeric_ratio * 0.60)


def score_account_series(s: pd.Series) -> float:
    codes = s.apply(extract_account_code)
    if len(codes) == 0:
        return 0.0

    # En el plan de cuentas actual, las cuentas suelen ser 6 dígitos.
    valid_len = codes.str.len().between(5, 8)
    valid_prefix = codes.str[0].isin(list("123456"))
    valid = valid_len & valid_prefix

    non_zero_numeric = codes.ne("")
    unique_ratio = codes[valid].nunique() / max(1, valid.sum())

    prefix_bonus = 0.0
    prefixes = set(codes[valid].str[0].dropna().tolist())
    if prefixes.intersection({"4", "5", "6"}):
        prefix_bonus += 0.20
    if prefixes.intersection({"1", "2", "3"}):
        prefix_bonus += 0.10
    if len(prefixes) >= 3:
        prefix_bonus += 0.10

    return float(valid.mean()) + prefix_bonus + min(unique_ratio, 1.0) * 0.10 + float(non_zero_numeric.mean()) * 0.05


def numeric_profile(s: pd.Series) -> tuple[pd.Series, float, float, float]:
    nums = s.apply(normalize_number)
    non_zero_ratio = float(nums.ne(0).mean()) if len(nums) else 0.0
    abs_sum = float(nums.abs().sum())
    max_abs = float(nums.abs().max()) if len(nums) else 0.0

    unique_abs = set(abs(float(x)) for x in nums.dropna().unique()[:20])
    binary_penalty = 0.50 if unique_abs and unique_abs.issubset({0.0, 1.0}) else 0.0
    large_bonus = 0.20 if max_abs > 1000 else 0.0
    score = non_zero_ratio + large_bonus - binary_penalty

    return nums, score, abs_sum, max_abs


def infer_no_header_columns(
    raw: pd.DataFrame,
    fecha_col_override: int | None = None,
    cuenta_col_override: int | None = None,
    debe_col_override: int | None = None,
    haber_col_override: int | None = None,
) -> list[str]:
    """
    Infere columnas en archivos sin headers.

    La clave es NO asumir posición fija de la cuenta contable.
    Se detecta:
    - Fecha: columna con mayor tasa de fechas.
    - Cuenta: columna con mayor tasa de códigos contables.
    - Debe/Haber: mejor par de columnas numéricas cuyo total queda más balanceado.
    """
    ncols = raw.shape[1]
    mapping: dict[int, str] = {}

    # Overrides manuales 1-based.
    if fecha_col_override:
        mapping[fecha_col_override - 1] = "fecha"
    if cuenta_col_override:
        mapping[cuenta_col_override - 1] = "cuenta_contable"
    if debe_col_override:
        mapping[debe_col_override - 1] = "debe_ml"
    if haber_col_override:
        mapping[haber_col_override - 1] = "haber_ml"

    for idx in mapping:
        if idx < 0 or idx >= ncols:
            raise ValueError(f"Columna override fuera de rango: {idx + 1}. El archivo tiene {ncols} columnas.")

    # Fecha.
    if "fecha" not in mapping.values():
        date_scores = [(i, score_date_series(raw.iloc[:, i])) for i in range(ncols) if i not in mapping]
        date_col, _ = max(date_scores, key=lambda x: x[1])
        mapping[date_col] = "fecha"

    # Cuenta contable.
    if "cuenta_contable" not in mapping.values():
        account_scores = [
            (i, score_account_series(raw.iloc[:, i]))
            for i in range(ncols)
            if i not in mapping
        ]
        account_col, account_score = max(account_scores, key=lambda x: x[1])
        if account_score < 0.45:
            raise ValueError(
                "No se pudo detectar de forma confiable la columna de cuenta contable. "
                "Usa --cuenta-col con número de columna 1-based."
            )
        mapping[account_col] = "cuenta_contable"
    else:
        account_col = [i for i, name in mapping.items() if name == "cuenta_contable"][0]

    # Debe/Haber.
    if "debe_ml" not in mapping.values() or "haber_ml" not in mapping.values():
        numeric_candidates = []
        for i in range(ncols):
            if i in mapping:
                continue
            nums, score, abs_sum, max_abs = numeric_profile(raw.iloc[:, i])
            # Evitar columnas sin montos reales.
            if score > 0.10 and abs_sum > 0:
                numeric_candidates.append((i, nums, score, abs_sum, max_abs))

        best_pair = None
        best_score = None

        for a_idx in range(len(numeric_candidates)):
            for b_idx in range(a_idx + 1, len(numeric_candidates)):
                i, nums_i, score_i, sum_i, _ = numeric_candidates[a_idx]
                j, nums_j, score_j, sum_j, _ = numeric_candidates[b_idx]

                total = sum_i + sum_j
                if total <= 0:
                    continue

                balance_ratio = abs(sum_i - sum_j) / total

                # Preferir columnas a la derecha de la cuenta y cercanas entre sí.
                right_bonus = 0.0
                if i > account_col and j > account_col:
                    right_bonus -= 0.15

                distance_penalty = abs(i - j) * 0.01

                score = balance_ratio + distance_penalty + right_bonus - (score_i + score_j) * 0.01

                if best_score is None or score < best_score:
                    best_score = score
                    best_pair = (i, j)

        if not best_pair:
            raise ValueError(
                "No se pudieron detectar columnas Debe/Haber. "
                "Usa --debe-col y --haber-col con números de columna 1-based."
            )

        amount_cols = sorted(best_pair)

        if "debe_ml" not in mapping.values():
            mapping[amount_cols[0]] = "debe_ml"
        if "haber_ml" not in mapping.values():
            mapping[amount_cols[1]] = "haber_ml"

    # Completar columnas restantes con nombres útiles.
    account_col = [i for i, name in mapping.items() if name == "cuenta_contable"][0]
    amount_cols = sorted([i for i, name in mapping.items() if name in {"debe_ml", "haber_ml"}])

    for i in range(ncols):
        if i in mapping:
            continue

        if i == 1:
            mapping[i] = "tipo_comprobante"
        elif i == 2:
            mapping[i] = "numero_comprobante"
        elif i == 3:
            mapping[i] = "secuencia"
        elif i < account_col:
            mapping[i] = "glosa" if "glosa" not in mapping.values() else f"extra_{i}"
        elif account_col < i < amount_cols[0]:
            mapping[i] = "cuenta_nombre" if "cuenta_nombre" not in mapping.values() else f"extra_{i}"
        else:
            mapping[i] = "ignorar" if "ignorar" not in mapping.values() else f"extra_{i}"

    required = {"fecha", "cuenta_contable", "debe_ml", "haber_ml"}
    missing = required - set(mapping.values())
    if missing:
        raise ValueError(f"No se pudieron inferir columnas mínimas: {missing}")

    print("\nDetección automática de columnas sin headers")
    print("-" * 80)
    for i in range(ncols):
        sample = raw.iloc[:3, i].tolist()
        print(f"Col {i + 1}: {mapping[i]:22} sample={sample}")

    return [mapping[i] for i in range(ncols)]


def read_excel_any(
    path: Path,
    fecha_col_override: int | None = None,
    cuenta_col_override: int | None = None,
    debe_col_override: int | None = None,
    haber_col_override: int | None = None,
) -> tuple[pd.DataFrame, bool]:
    raw = pd.read_excel(path, header=None, dtype=object)
    raw = raw.dropna(how="all")

    if raw.empty:
        raise ValueError("El archivo no tiene filas útiles.")

    has_header = looks_like_header(raw.iloc[0])

    if has_header:
        header = [normalize_col_name(x) for x in raw.iloc[0].tolist()]
        df = raw.iloc[1:].copy()
        df.columns = header

        rename: dict[str, str] = {}
        for canonical, aliases in COLUMN_ALIASES.items():
            for col in df.columns:
                if col in aliases:
                    if canonical not in rename.values():
                        rename[col] = canonical
                    break

        df = df.rename(columns=rename)
        df = df.loc[:, ~df.columns.duplicated()].copy()

    else:
        df = raw.copy()
        cols = infer_no_header_columns(
            raw,
            fecha_col_override=fecha_col_override,
            cuenta_col_override=cuenta_col_override,
            debe_col_override=debe_col_override,
            haber_col_override=haber_col_override,
        )
        df.columns = cols

    return df, has_header


def normalize_libro(
    path: Path,
    empresa: str,
    oficina: str,
    fecha_col_override: int | None = None,
    cuenta_col_override: int | None = None,
    debe_col_override: int | None = None,
    haber_col_override: int | None = None,
) -> tuple[pd.DataFrame, bool, str]:
    df, has_header = read_excel_any(
        path,
        fecha_col_override=fecha_col_override,
        cuenta_col_override=cuenta_col_override,
        debe_col_override=debe_col_override,
        haber_col_override=haber_col_override,
    )
    sha = file_sha256(path)

    required = ["fecha", "cuenta_contable", "debe_ml", "haber_ml"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas mínimas: {missing}. Columnas detectadas: {list(df.columns)}")

    for col in ["tipo_comprobante", "numero_comprobante", "secuencia", "glosa", "cuenta_nombre"]:
        if col not in df.columns:
            df[col] = ""

    fecha_series = pd.to_datetime(get_col(df, "fecha"), errors="coerce", dayfirst=True)
    cuenta_contable_series = get_col(df, "cuenta_contable")
    cuenta_nombre_series = get_col(df, "cuenta_nombre")
    debe_series = get_col(df, "debe_ml", 0)
    haber_series = get_col(df, "haber_ml", 0)

    out = pd.DataFrame(index=df.index)
    out["empresa"] = empresa
    out["oficina"] = oficina
    out["fecha"] = fecha_series.dt.date
    out["periodo"] = fecha_series.dt.strftime("%Y-%m")

    out["tipo_comprobante"] = get_col(df, "tipo_comprobante").fillna("").astype(str).str.strip()
    out["numero_comprobante"] = get_col(df, "numero_comprobante").fillna("").astype(str).str.strip()
    out["secuencia"] = get_col(df, "secuencia").fillna("").astype(str).str.strip()
    out["glosa"] = get_col(df, "glosa").fillna("").astype(str).str.strip()

    out["cuenta_contable"] = cuenta_contable_series.fillna("").astype(str).str.strip()
    out["cuenta_codigo"] = cuenta_contable_series.apply(extract_account_code)
    out["cuenta_nombre"] = [
        extract_account_name(c, n)
        for c, n in zip(cuenta_contable_series, cuenta_nombre_series)
    ]

    out["debe_ml"] = debe_series.apply(normalize_number)
    out["haber_ml"] = haber_series.apply(normalize_number)
    out["saldo_ml"] = out["haber_ml"] - out["debe_ml"]

    out["cuenta_eerr"] = out["cuenta_codigo"].str[0].isin(["4", "5", "6"]).map({True: "EERR", False: "BALANCE"})
    out["line_number"] = range(1, len(out) + 1)
    out["file_sha256"] = sha

    out = out.dropna(subset=["fecha"])
    out = out[out["cuenta_codigo"] != ""]
    out = out[(out["debe_ml"] != 0) | (out["haber_ml"] != 0)].copy()

    return out, has_header, sha


def print_summary(df: pd.DataFrame, path: Path, empresa: str, oficina: str, has_header: bool, sha: str) -> None:
    print("\nResumen de carga")
    print("-" * 80)
    print(f"Archivo:        {path}")
    print(f"SHA256:         {sha}")
    print(f"Headers:        {'sí' if has_header else 'no'}")
    print(f"Empresa:        {empresa}")
    print(f"Oficina:        {oficina}")
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
        .agg(
            filas=("cuenta_codigo", "size"),
            debe_ml=("debe_ml", "sum"),
            haber_ml=("haber_ml", "sum"),
            saldo_ml=("saldo_ml", "sum"),
        )
        .sort_values(["periodo", "cuenta_eerr"])
    )
    print("\nResumen mensual")
    print(monthly.to_string(index=False))

    by_prefix = (
        df.groupby(df["cuenta_codigo"].str[0], as_index=True)
        .agg(
            filas=("cuenta_codigo", "size"),
            debe_ml=("debe_ml", "sum"),
            haber_ml=("haber_ml", "sum"),
            saldo_ml=("saldo_ml", "sum"),
        )
        .reset_index()
        .rename(columns={"cuenta_codigo": "clase_cuenta"})
        .sort_values("clase_cuenta")
    )
    print("\nResumen por clase de cuenta")
    print(by_prefix.to_string(index=False))

    eerr = (
        df[df["cuenta_eerr"] == "EERR"]
        .groupby(["cuenta_codigo", "cuenta_nombre"], as_index=False)
        .agg(
            saldo_ml=("saldo_ml", "sum"),
            debe_ml=("debe_ml", "sum"),
            haber_ml=("haber_ml", "sum"),
        )
    )

    if not eerr.empty:
        eerr["abs_saldo"] = eerr["saldo_ml"].abs()
        eerr = eerr.sort_values("abs_saldo", ascending=False).head(20)
        eerr["cuenta_contable"] = eerr["cuenta_codigo"] + " - " + eerr["cuenta_nombre"]
        print("\nTop cuentas EERR por monto absoluto")
        print(eerr[["cuenta_contable", "saldo_ml", "debe_ml", "haber_ml"]].to_string(index=False))


def reset_schema(conn: psycopg.Connection, schema: str) -> None:
    schema = sanitize_schema(schema)
    with conn.cursor() as cur:
        cur.execute(f"drop schema if exists {schema} cascade;")
        cur.execute(f"create schema {schema};")


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
            oficina text not null,
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
            oficina text not null,
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

        cur.execute(f"alter table {schema}.cargas_libro_diario add column if not exists oficina text;")
        cur.execute(f"alter table {schema}.fact_libro_diario add column if not exists oficina text;")
        cur.execute(f"alter table {schema}.fact_libro_diario add column if not exists saldo_ml numeric(18,2) not null default 0;")
        cur.execute(f"alter table {schema}.cargas_libro_diario add column if not exists saldo_ml numeric(18,2) not null default 0;")

        cur.execute(f"update {schema}.cargas_libro_diario set oficina = empresa where oficina is null;")
        cur.execute(f"update {schema}.fact_libro_diario set oficina = empresa where oficina is null;")
        cur.execute(f"update {schema}.fact_libro_diario set saldo_ml = coalesce(haber_ml,0) - coalesce(debe_ml,0) where saldo_ml is null;")
        cur.execute(f"update {schema}.cargas_libro_diario set saldo_ml = coalesce(haber_ml,0) - coalesce(debe_ml,0) where saldo_ml is null;")

        cur.execute(f"create index if not exists idx_fact_libro_empresa_periodo on {schema}.fact_libro_diario (empresa, periodo);")
        cur.execute(f"create index if not exists idx_fact_libro_oficina_periodo on {schema}.fact_libro_diario (oficina, periodo);")
        cur.execute(f"create index if not exists idx_fact_libro_cuenta on {schema}.fact_libro_diario (cuenta_codigo);")
        cur.execute(f"create index if not exists idx_fact_libro_carga on {schema}.fact_libro_diario (carga_id);")

        cur.execute(f"""
        create or replace view {schema}.v_resumen_cargas as
        select
            id as carga_id,
            empresa,
            oficina,
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
            oficina,
            periodo,
            cuenta_codigo,
            cuenta_nombre,
            sum(debe_ml) as debe_ml,
            sum(haber_ml) as haber_ml,
            sum(saldo_ml) as saldo_ml,
            count(*) as movimientos
        from {schema}.fact_libro_diario
        where cuenta_eerr = 'EERR'
        group by empresa, oficina, periodo, cuenta_codigo, cuenta_nombre;
        """)

        for emp in EMPRESAS:
            cur.execute(
                f"insert into {schema}.empresas(nombre) values (%s) on conflict (nombre) do nothing;",
                (emp,),
            )


def insert_libro(
    conn: psycopg.Connection,
    df: pd.DataFrame,
    schema: str,
    path: Path,
    sha: str,
    replace: bool,
) -> int:
    schema = sanitize_schema(schema)
    empresa = str(df["empresa"].iloc[0])
    oficina = str(df["oficina"].iloc[0])

    with conn.cursor(row_factory=dict_row) as cur:
        if replace:
            cur.execute(
                f"delete from {schema}.cargas_libro_diario where oficina = %s and file_sha256 = %s;",
                (oficina, sha),
            )

        cur.execute(f"""
            insert into {schema}.cargas_libro_diario (
                empresa, oficina, archivo_nombre, file_sha256, filas, fecha_min, fecha_max,
                debe_ml, haber_ml, saldo_ml, metadata
            )
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            returning id;
        """, (
            empresa,
            oficina,
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
                r["oficina"],
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
                carga_id, empresa, oficina, periodo, fecha, tipo_comprobante, numero_comprobante,
                secuencia, glosa, cuenta_codigo, cuenta_nombre, cuenta_contable,
                debe_ml, haber_ml, saldo_ml, cuenta_eerr, line_number, file_sha256
            )
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
        """, rows)

    return carga_id


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("archivo", help="Archivo .xls/.xlsx de libro diario")
    parser.add_argument("--empresa", choices=EMPRESAS)
    parser.add_argument("--oficina", help="Oficina operativa. Si no se entrega, se usa empresa.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--schema", default=os.getenv("FINANZAS_SCHEMA", "finanzas"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true", help="Reemplaza cargas con misma oficina+hash")
    parser.add_argument("--reset-schema", action="store_true", help="DANGER: borra completamente el schema antes de cargar")
    parser.add_argument("--export-csv")
    parser.add_argument("--fecha-col", type=int, help="Override 1-based para columna fecha en archivos sin headers")
    parser.add_argument("--cuenta-col", type=int, help="Override 1-based para columna cuenta contable en archivos sin headers")
    parser.add_argument("--debe-col", type=int, help="Override 1-based para columna debe en archivos sin headers")
    parser.add_argument("--haber-col", type=int, help="Override 1-based para columna haber en archivos sin headers")

    args = parser.parse_args()

    path = Path(args.archivo)
    if not path.exists():
        print(f"No existe el archivo: {path}", file=sys.stderr)
        return 1

    empresa = args.empresa or choose_empresa()
    oficina = args.oficina or empresa

    df, has_header, sha = normalize_libro(
        path,
        empresa,
        oficina,
        fecha_col_override=args.fecha_col,
        cuenta_col_override=args.cuenta_col,
        debe_col_override=args.debe_col,
        haber_col_override=args.haber_col,
    )

    print_summary(df, path, empresa, oficina, has_header, sha)

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
        if args.reset_schema:
            print(f"\nATENCIÓN: borrando schema completo: {schema}")
            reset_schema(conn, schema)

        ensure_schema_and_tables(conn, schema)
        carga_id = insert_libro(conn, df, schema, path, sha, args.replace)
        conn.commit()

    print(f"\nCarga completada en Postgres. carga_id={carga_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
