#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Carga mapping PNL versionable desde JSON a Neon/Postgres.

Uso:
  python load_pnl_mapping_from_config.py config/pnl_mapping_rules.json --dry-run
  python load_pnl_mapping_from_config.py config/pnl_mapping_rules.json --replace
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row


VALID_RULE_TYPES = {"exact", "prefix", "default"}


def sanitize_schema(schema: str) -> str:
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", schema):
        raise ValueError(f"Schema inválido: {schema}")
    return schema


def normalize_pattern(pattern: Any, rule_type: str) -> str:
    if rule_type == "default":
        return ""
    if pattern is None:
        return ""
    return re.sub(r"\D", "", str(pattern).strip())


def load_config(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rules = payload.get("rules", payload if isinstance(payload, list) else [])
    if not isinstance(rules, list):
        raise ValueError("El archivo debe contener una lista de rules o un objeto con propiedad 'rules'.")

    out = []
    seen = set()

    for i, rule in enumerate(rules, 1):
        rule_type = str(rule.get("rule_type", "")).strip().lower()
        if rule_type not in VALID_RULE_TYPES:
            raise ValueError(f"Regla {i}: rule_type inválido: {rule_type}")

        pattern = normalize_pattern(rule.get("pattern", ""), rule_type)
        if rule_type in {"exact", "prefix"} and not pattern:
            raise ValueError(f"Regla {i}: pattern vacío para rule_type={rule_type}")

        rule_key = str(rule.get("rule_key") or f"{rule_type}_{pattern}_{i}").strip()
        if rule_key in seen:
            raise ValueError(f"rule_key duplicado: {rule_key}")
        seen.add(rule_key)

        out.append({
            "rule_key": rule_key,
            "rule_type": rule_type,
            "pattern": pattern,
            "priority": int(rule.get("priority", 100)),
            "orden": int(rule.get("orden", 9999)),
            "nivel1": str(rule.get("nivel1", "SIN MAPEO")).strip(),
            "nivel2": str(rule.get("nivel2", "SIN MAPEO")).strip(),
            "nivel3": str(rule.get("nivel3", "SIN MAPEO")).strip(),
            "is_fallback": bool(rule.get("is_fallback", False)),
            "activa": bool(rule.get("activa", True)),
            "description": str(rule.get("description", "")).strip(),
        })

    return out


def ensure_tables(conn: psycopg.Connection, schema: str) -> None:
    schema = sanitize_schema(schema)
    with conn.cursor() as cur:
        cur.execute(f"create schema if not exists {schema};")

        cur.execute(f"""
        create table if not exists {schema}.dim_pnl_mapping_rule (
            id bigserial primary key,
            rule_key text not null unique,
            rule_type text not null check (rule_type in ('exact','prefix','default')),
            pattern text not null default '',
            priority integer not null default 100,
            orden integer not null default 9999,
            nivel1 text not null,
            nivel2 text not null,
            nivel3 text not null,
            is_fallback boolean not null default false,
            activa boolean not null default true,
            description text,
            created_at timestamptz not null default now()
        );
        """)

        cur.execute(f"create index if not exists idx_dim_pnl_rule_match on {schema}.dim_pnl_mapping_rule (activa, rule_type, pattern);")
        cur.execute(f"create index if not exists idx_dim_pnl_rule_order on {schema}.dim_pnl_mapping_rule (priority desc, orden);")

        # Views are useful in Neon, even if Evidence also has explicit queries.
        cur.execute(f"""
        create or replace view {schema}.v_pnl_movimientos_config as
        select
            f.id as movimiento_id,
            f.carga_id,
            f.empresa,
            f.periodo,
            f.fecha,
            f.cuenta_codigo,
            f.cuenta_nombre,
            f.cuenta_contable,
            f.glosa,
            f.debe_ml,
            f.haber_ml,
            f.saldo_ml,
            r.id as rule_id,
            r.rule_key,
            r.rule_type,
            r.pattern,
            r.priority,
            r.orden,
            r.nivel1,
            r.nivel2,
            r.nivel3,
            coalesce(r.is_fallback, true) as is_fallback
        from {schema}.fact_libro_diario f
        left join lateral (
            select *
            from {schema}.dim_pnl_mapping_rule r
            where r.activa = true
              and (
                    (r.rule_type = 'exact' and r.pattern = f.cuenta_codigo)
                 or (r.rule_type = 'prefix' and left(f.cuenta_codigo, length(r.pattern)) = r.pattern)
                 or (r.rule_type = 'default')
              )
            order by r.priority desc, length(r.pattern) desc, r.orden asc, r.id asc
            limit 1
        ) r on true
        where left(f.cuenta_codigo, 1) in ('4','5','6');
        """)

        cur.execute(f"""
        create or replace view {schema}.v_pnl_mensual_config as
        select
            empresa,
            periodo,
            orden,
            nivel1,
            nivel2,
            nivel3,
            is_fallback,
            sum(saldo_ml) as monto_ml,
            count(*) as movimientos
        from {schema}.v_pnl_movimientos_config
        group by empresa, periodo, orden, nivel1, nivel2, nivel3, is_fallback;
        """)

        cur.execute(f"""
        create or replace view {schema}.v_pnl_cuentas_fallback_config as
        select
            empresa,
            cuenta_codigo,
            cuenta_nombre,
            min(orden) as orden,
            min(nivel1) as nivel1,
            min(nivel2) as nivel2,
            min(nivel3) as nivel3,
            sum(saldo_ml) as monto_ml,
            count(*) as movimientos
        from {schema}.v_pnl_movimientos_config
        where is_fallback = true
        group by empresa, cuenta_codigo, cuenta_nombre;
        """)


def upsert_rules(conn: psycopg.Connection, schema: str, rules: list[dict[str, Any]], replace: bool) -> None:
    schema = sanitize_schema(schema)
    with conn.cursor() as cur:
        if replace:
            cur.execute(f"truncate table {schema}.dim_pnl_mapping_rule restart identity;")

        cur.executemany(f"""
            insert into {schema}.dim_pnl_mapping_rule (
                rule_key, rule_type, pattern, priority, orden,
                nivel1, nivel2, nivel3, is_fallback, activa, description
            )
            values (%(rule_key)s, %(rule_type)s, %(pattern)s, %(priority)s, %(orden)s,
                    %(nivel1)s, %(nivel2)s, %(nivel3)s, %(is_fallback)s, %(activa)s, %(description)s)
            on conflict (rule_key) do update set
                rule_type = excluded.rule_type,
                pattern = excluded.pattern,
                priority = excluded.priority,
                orden = excluded.orden,
                nivel1 = excluded.nivel1,
                nivel2 = excluded.nivel2,
                nivel3 = excluded.nivel3,
                is_fallback = excluded.is_fallback,
                activa = excluded.activa,
                description = excluded.description;
        """, rules)


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="Ruta a config/pnl_mapping_rules.json")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--schema", default=os.getenv("FINANZAS_SCHEMA", "finanzas"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    path = Path(args.config)
    if not path.exists():
        print(f"No existe el archivo: {path}", file=sys.stderr)
        return 1

    rules = load_config(path)

    print("\nResumen mapping PNL")
    print("-" * 80)
    print(f"Archivo:        {path}")
    print(f"Reglas:         {len(rules)}")
    print(f"Exactas:        {sum(1 for r in rules if r['rule_type'] == 'exact')}")
    print(f"Prefijos:       {sum(1 for r in rules if r['rule_type'] == 'prefix')}")
    print(f"Default:        {sum(1 for r in rules if r['rule_type'] == 'default')}")
    print(f"Fallback:       {sum(1 for r in rules if r['is_fallback'])}")

    for r in sorted(rules, key=lambda x: (-x["priority"], x["orden"], x["pattern"]))[:20]:
        print(f"- {r['rule_type']:6} {r['pattern'] or '<default>':8} prio={r['priority']:4} orden={r['orden']:4} {r['nivel1']} / {r['nivel2']}")

    if args.dry_run:
        print("\nDry run: no se cargó a Postgres.")
        return 0

    if not args.database_url:
        print("\nFalta DATABASE_URL. Agrégalo a .env o usa --database-url.", file=sys.stderr)
        return 1

    schema = sanitize_schema(args.schema)
    with psycopg.connect(args.database_url) as conn:
        ensure_tables(conn, schema)
        upsert_rules(conn, schema, rules, args.replace)
        conn.commit()

    print(f"\nMapping PNL cargado en {schema}.dim_pnl_mapping_rule")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
