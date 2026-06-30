#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LEGACY / opcional.

Carga dimensiones PNL desde un XLSX con pestañas tipo:
- Cuentas
- Estructura
- P&L Layout

La estrategia recomendada para producción es usar:
  load_pnl_mapping_from_config.py config/pnl_mapping_rules.json

Este script queda incluido solo para rescatar o comparar la lógica histórica del Excel.
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
import psycopg


def sanitize_schema(schema: str) -> str:
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", schema):
        raise ValueError(f"Schema inválido: {schema}")
    return schema


def clean_col(col) -> str:
    text = str(col).strip().lower()
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", "_", text)
    text = text.replace("&", "y")
    text = re.sub(r"[^a-z0-9_áéíóúñ]", "", text)
    return text


def account_code(value) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\D", "", str(value))


def find_sheet(xls: pd.ExcelFile, candidates: list[str]) -> str | None:
    names = {s.strip().lower(): s for s in xls.sheet_names}
    for c in candidates:
        if c.strip().lower() in names:
            return names[c.strip().lower()]
    for s in xls.sheet_names:
        low = s.strip().lower()
        if any(c.strip().lower() in low for c in candidates):
            return s
    return None


def load_sheet(path: Path, sheet: str | None) -> pd.DataFrame:
    if sheet is None:
        return pd.DataFrame()
    df = pd.read_excel(path, sheet_name=sheet, dtype=object)
    df.columns = [clean_col(c) for c in df.columns]
    df = df.dropna(how="all")
    return df


def create_tables(conn, schema: str):
    with conn.cursor() as cur:
        cur.execute(f"create schema if not exists {schema};")
        cur.execute(f"""
        create table if not exists {schema}.dim_cuenta_pnl (
            cuenta_codigo text primary key,
            cuenta_nombre text,
            nivel1 text,
            nivel2 text,
            nivel3 text,
            source text,
            created_at timestamptz not null default now()
        );
        """)
        cur.execute(f"""
        create table if not exists {schema}.dim_pnl_estructura (
            id bigserial primary key,
            orden integer,
            nivel1 text,
            nivel2 text,
            nivel3 text,
            tipo_fila text,
            created_at timestamptz not null default now()
        );
        """)
        cur.execute(f"""
        create table if not exists {schema}.dim_pnl_layout (
            id bigserial primary key,
            orden integer,
            linea text,
            nivel1 text,
            nivel2 text,
            tipo_fila text,
            created_at timestamptz not null default now()
        );
        """)


def guess_col(df: pd.DataFrame, aliases: list[str]) -> str | None:
    for alias in aliases:
        a = clean_col(alias)
        if a in df.columns:
            return a
    for c in df.columns:
        if any(clean_col(alias) in c for alias in aliases):
            return c
    return None


def main():
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("xlsx")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--schema", default=os.getenv("FINANZAS_SCHEMA", "finanzas"))
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    path = Path(args.xlsx)
    schema = sanitize_schema(args.schema)

    xls = pd.ExcelFile(path)
    sheet_cuentas = find_sheet(xls, ["Cuentas", "Cuenta"])
    sheet_estructura = find_sheet(xls, ["Estructura"])
    sheet_layout = find_sheet(xls, ["P&L Layout", "P L Layout", "Layout"])

    cuentas = load_sheet(path, sheet_cuentas)
    estructura = load_sheet(path, sheet_estructura)
    layout = load_sheet(path, sheet_layout)

    print("\nDimensiones detectadas")
    print("-" * 80)
    print(f"Sheet Cuentas:    {sheet_cuentas} ({len(cuentas)} filas)")
    print(f"Sheet Estructura: {sheet_estructura} ({len(estructura)} filas)")
    print(f"Sheet Layout:     {sheet_layout} ({len(layout)} filas)")

    if args.dry_run:
        print("\nDry run: no se cargó a Postgres.")
        return

    if not args.database_url:
        raise SystemExit("Falta DATABASE_URL")

    with psycopg.connect(args.database_url) as conn:
        create_tables(conn, schema)

        with conn.cursor() as cur:
            if args.replace:
                cur.execute(f"truncate table {schema}.dim_cuenta_pnl;")
                cur.execute(f"truncate table {schema}.dim_pnl_estructura restart identity;")
                cur.execute(f"truncate table {schema}.dim_pnl_layout restart identity;")

            if not cuentas.empty:
                c_cuenta = guess_col(cuentas, ["cuenta", "cuenta_codigo", "codigo", "código"])
                c_nombre = guess_col(cuentas, ["nombre", "glosa cuenta", "cuenta_nombre"])
                c_n1 = guess_col(cuentas, ["nivel 1", "nivel1"])
                c_n2 = guess_col(cuentas, ["nivel 2", "nivel2"])
                c_n3 = guess_col(cuentas, ["nivel 3", "nivel3"])

                rows = []
                for _, r in cuentas.iterrows():
                    code = account_code(r.get(c_cuenta)) if c_cuenta else ""
                    if not code:
                        continue
                    rows.append((
                        code,
                        str(r.get(c_nombre, "") or "").strip(),
                        str(r.get(c_n1, "") or "").strip(),
                        str(r.get(c_n2, "") or "").strip(),
                        str(r.get(c_n3, "") or "").strip(),
                        path.name,
                    ))

                cur.executemany(f"""
                    insert into {schema}.dim_cuenta_pnl
                    (cuenta_codigo, cuenta_nombre, nivel1, nivel2, nivel3, source)
                    values (%s,%s,%s,%s,%s,%s)
                    on conflict (cuenta_codigo) do update set
                        cuenta_nombre = excluded.cuenta_nombre,
                        nivel1 = excluded.nivel1,
                        nivel2 = excluded.nivel2,
                        nivel3 = excluded.nivel3,
                        source = excluded.source;
                """, rows)

            if not estructura.empty:
                c_orden = guess_col(estructura, ["orden"])
                c_n1 = guess_col(estructura, ["nivel 1", "nivel1"])
                c_n2 = guess_col(estructura, ["nivel 2", "nivel2"])
                c_n3 = guess_col(estructura, ["nivel 3", "nivel3"])
                c_tipo = guess_col(estructura, ["tipo", "tipo fila", "tipo_fila"])

                rows = []
                for _, r in estructura.iterrows():
                    rows.append((
                        int(r.get(c_orden) or 9999) if c_orden else 9999,
                        str(r.get(c_n1, "") or "").strip(),
                        str(r.get(c_n2, "") or "").strip(),
                        str(r.get(c_n3, "") or "").strip(),
                        str(r.get(c_tipo, "detalle") or "detalle").strip(),
                    ))

                cur.executemany(f"""
                    insert into {schema}.dim_pnl_estructura
                    (orden, nivel1, nivel2, nivel3, tipo_fila)
                    values (%s,%s,%s,%s,%s);
                """, rows)

            if not layout.empty:
                c_orden = guess_col(layout, ["orden"])
                c_linea = guess_col(layout, ["linea", "línea", "nombre"])
                c_n1 = guess_col(layout, ["nivel 1", "nivel1"])
                c_n2 = guess_col(layout, ["nivel 2", "nivel2"])
                c_tipo = guess_col(layout, ["tipo", "tipo fila", "tipo_fila"])

                rows = []
                for _, r in layout.iterrows():
                    rows.append((
                        int(r.get(c_orden) or 9999) if c_orden else 9999,
                        str(r.get(c_linea, "") or "").strip(),
                        str(r.get(c_n1, "") or "").strip(),
                        str(r.get(c_n2, "") or "").strip(),
                        str(r.get(c_tipo, "detalle") or "detalle").strip(),
                    ))

                cur.executemany(f"""
                    insert into {schema}.dim_pnl_layout
                    (orden, linea, nivel1, nivel2, tipo_fila)
                    values (%s,%s,%s,%s,%s);
                """, rows)

        conn.commit()

    print("\nDimensiones históricas cargadas. Para producción usa el JSON versionable.")


if __name__ == "__main__":
    main()
