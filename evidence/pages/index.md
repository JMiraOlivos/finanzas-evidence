---
title: EERR Finanzas
---

# EERR Finanzas

Primera versión de reportería financiera con Neon Postgres + Evidence.

## Últimas cargas

```sql cargas
select
    id,
    empresa_id,
    archivo_nombre,
    filas_leidas,
    filas_insertadas,
    fecha_min,
    fecha_max,
    total_debe_ml,
    total_haber_ml,
    (total_debe_ml - total_haber_ml) as saldo_ml,
    creado_en
from postgres_finanzas_cargas_libro_diario
order by id desc
```

{% table data="cargas" /%}

## Resultado mensual

```sql resultado_mensual
with movimientos_pnl as (
    select f.id, f.empresa, f.periodo, f.cuenta_codigo, f.saldo_ml
    from postgres_finanzas_fact_libro_diario f
    where substring(f.cuenta_codigo, 1, 1) in ('4','5','6')
),
candidatos as (
    select m.*, r.orden, r.nivel1,
        row_number() over (
            partition by m.id
            order by coalesce(r.priority,-999999) desc,
                length(coalesce(r.pattern,'')) desc,
                coalesce(r.orden,9999) asc,
                coalesce(r.id,999999999) asc
        ) as rn
    from movimientos_pnl m
    cross join postgres_finanzas_dim_pnl_mapping_rule r
    where r.activa = true
      and (
           (r.rule_type='exact' and r.pattern = m.cuenta_codigo)
        or (r.rule_type='prefix' and substring(m.cuenta_codigo,1,length(r.pattern)) = r.pattern)
        or (r.rule_type='default')
      )
),
base as (
    select empresa, periodo, saldo_ml, coalesce(nivel1,'SIN MAPEO') as nivel1
    from candidatos where rn = 1
)
select empresa, periodo,
    sum(case when nivel1='Ingresos' then saldo_ml else 0 end) as ingresos_ml,
    sum(case when nivel1!='Ingresos' then saldo_ml else 0 end) as gastos_ml,
    sum(saldo_ml) as resultado_ml
from base group by empresa, periodo order by empresa, periodo
```

{% table data="resultado_mensual" /%}

## PNL por Nivel 1

```sql pnl_nivel1
with movimientos_pnl as (
    select f.id, f.empresa, f.periodo, f.cuenta_codigo, f.saldo_ml
    from postgres_finanzas_fact_libro_diario f
    where substring(f.cuenta_codigo, 1, 1) in ('4','5','6')
),
candidatos as (
    select m.*, r.orden, r.nivel1,
        row_number() over (
            partition by m.id
            order by coalesce(r.priority,-999999) desc,
                length(coalesce(r.pattern,'')) desc,
                coalesce(r.orden,9999) asc,
                coalesce(r.id,999999999) asc
        ) as rn
    from movimientos_pnl m
    cross join postgres_finanzas_dim_pnl_mapping_rule r
    where r.activa = true
      and (
           (r.rule_type='exact' and r.pattern = m.cuenta_codigo)
        or (r.rule_type='prefix' and substring(m.cuenta_codigo,1,length(r.pattern)) = r.pattern)
        or (r.rule_type='default')
      )
),
base as (
    select empresa, periodo, saldo_ml,
        coalesce(orden,9999) as orden,
        coalesce(nivel1,'SIN MAPEO') as nivel1
    from candidatos where rn = 1
)
select empresa, periodo, orden, nivel1,
    sum(saldo_ml) as monto_ml,
    count(*) as movimientos
from base group by empresa, periodo, orden, nivel1
order by empresa, periodo, orden, nivel1
```

{% table data="pnl_nivel1" /%}

## PNL estructurado

```sql pnl_estructurado
with movimientos_pnl as (
    select f.id, f.empresa, f.periodo, f.cuenta_codigo, f.saldo_ml
    from postgres_finanzas_fact_libro_diario f
    where substring(f.cuenta_codigo, 1, 1) in ('4','5','6')
),
candidatos as (
    select m.*, r.orden, r.nivel1, r.nivel2, r.nivel3, r.is_fallback,
        row_number() over (
            partition by m.id
            order by coalesce(r.priority,-999999) desc,
                length(coalesce(r.pattern,'')) desc,
                coalesce(r.orden,9999) asc,
                coalesce(r.id,999999999) asc
        ) as rn
    from movimientos_pnl m
    cross join postgres_finanzas_dim_pnl_mapping_rule r
    where r.activa = true
      and (
           (r.rule_type='exact' and r.pattern = m.cuenta_codigo)
        or (r.rule_type='prefix' and substring(m.cuenta_codigo,1,length(r.pattern)) = r.pattern)
        or (r.rule_type='default')
      )
),
base as (
    select empresa, periodo, saldo_ml,
        coalesce(orden,9999) as orden,
        coalesce(nivel1,'SIN MAPEO') as nivel1,
        coalesce(nivel2,'SIN MAPEO') as nivel2,
        coalesce(nivel3,'SIN MAPEO') as nivel3,
        coalesce(is_fallback,true) as is_fallback
    from candidatos where rn = 1
)
select empresa, periodo, orden, nivel1, nivel2, nivel3,
    sum(saldo_ml) as monto_ml,
    count(*) as movimientos,
    max(is_fallback) as contiene_fallback
from base group by empresa, periodo, orden, nivel1, nivel2, nivel3
order by empresa, periodo, orden, nivel1, nivel2, nivel3
```

{% table data="pnl_estructurado" /%}

## Cuentas por revisar

Estas cuentas están siendo procesadas por fallback o quedaron sin clasificación específica. La idea es ir agregando reglas exactas en `etl/config/pnl_mapping_rules.json`.

```sql cuentas_revision
with movimientos_pnl as (
    select f.id, f.empresa, f.periodo, f.cuenta_codigo, f.cuenta_nombre, f.saldo_ml
    from postgres_finanzas_fact_libro_diario f
    where substring(f.cuenta_codigo, 1, 1) in ('4','5','6')
),
candidatos as (
    select m.*, r.rule_key, r.rule_type, r.nivel1, r.nivel2, r.nivel3, r.is_fallback,
        row_number() over (
            partition by m.id
            order by coalesce(r.priority,-999999) desc,
                length(coalesce(r.pattern,'')) desc,
                coalesce(r.orden,9999) asc,
                coalesce(r.id,999999999) asc
        ) as rn
    from movimientos_pnl m
    cross join postgres_finanzas_dim_pnl_mapping_rule r
    where r.activa = true
      and (
           (r.rule_type='exact' and r.pattern = m.cuenta_codigo)
        or (r.rule_type='prefix' and substring(m.cuenta_codigo,1,length(r.pattern)) = r.pattern)
        or (r.rule_type='default')
      )
),
base as (
    select empresa, cuenta_codigo, cuenta_nombre, saldo_ml,
        coalesce(rule_key,'sin_regla') as rule_key,
        coalesce(rule_type,'none') as rule_type,
        coalesce(nivel1,'SIN MAPEO') as nivel1,
        coalesce(nivel2,'SIN MAPEO') as nivel2,
        coalesce(nivel3,'SIN MAPEO') as nivel3,
        coalesce(is_fallback,true) as is_fallback
    from candidatos where rn = 1
),
agg as (
    select empresa, cuenta_codigo,
        any(cuenta_nombre) as cuenta_nombre,
        any(rule_key) as regla_aplicada,
        any(rule_type) as tipo_regla,
        any(nivel1) as nivel1_agg,
        any(nivel2) as nivel2_agg,
        any(nivel3) as nivel3_agg,
        sum(saldo_ml) as monto_ml,
        count(*) as movimientos,
        max(is_fallback) as tiene_fallback,
        countIf(nivel1 in ('SIN MAPEO', 'P&L sin clasificar')) as sin_clasificar
    from base
    group by empresa, cuenta_codigo
)
select empresa, cuenta_codigo, cuenta_nombre, regla_aplicada, tipo_regla,
    nivel1_agg as nivel1, nivel2_agg as nivel2, nivel3_agg as nivel3,
    monto_ml, movimientos
from agg
where tiene_fallback = true or sin_clasificar > 0
order by abs(monto_ml) desc
```

{% table data="cuentas_revision" /%}
