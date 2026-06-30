---
title: EERR Finanzas
---

# EERR Finanzas

Primera versión conectada a Neon Postgres.

```sql cargas
select *
from postgres_finanzas_cargas_libro_diario
order by id desc
```

## Últimas cargas

{% table data="cargas" /%}

```sql eerr_mensual
select
    empresa,
    periodo,
    cuenta_codigo,
    cuenta_nombre,
    debe_ml,
    haber_ml,
    saldo_ml
from postgres_finanzas_fact_libro_diario
order by periodo, cuenta_codigo
```

## EERR mensual por cuenta

{% table data="eerr_mensual" /%}

```sql resumen_mes
select
    periodo,
    sum(case when saldo_ml > 0 then saldo_ml else 0 end) as ingresos,
    sum(case when saldo_ml < 0 then saldo_ml else 0 end) as gastos,
    sum(saldo_ml) as resultado
from postgres_finanzas_fact_libro_diario
group by periodo
order by periodo
```

## Resultado mensual

## PNL básico

```sql pnl_base
select
    empresa,
    periodo,
    cuenta_codigo,
    cuenta_nombre,
    substr(cast(cuenta_codigo as varchar), 1, 1) as clase_cuenta,
    debe_ml,
    haber_ml,
    coalesce(haber_ml, 0) - coalesce(debe_ml, 0) as saldo_pnl_ml,
    case
        when substr(cast(cuenta_codigo as varchar), 1, 1) = '5' then 'Ingresos'
        when substr(cast(cuenta_codigo as varchar), 1, 1) in ('4', '6') then 'Gastos'
        else 'Otro'
    end as tipo_pnl
from postgres_finanzas_fact_libro_diario
where substr(cast(cuenta_codigo as varchar), 1, 1) in ('4', '5', '6')
```

{% table data="pnl_base" /%}

## PNL ordenado

```sql pnl_layout
select
    f.empresa,
    f.periodo,
    d.nivel1,
    d.nivel2 as linea_pnl,
    sum(coalesce(f.haber_ml, 0) - coalesce(f.debe_ml, 0)) as monto_ml
from postgres_finanzas_fact_libro_diario f
left join postgres_finanzas_dim_cuenta_pnl d
    on f.cuenta_codigo = d.cuenta_codigo
where f.es_pnl = true
group by f.empresa, f.periodo, d.nivel1, d.nivel2
order by f.empresa, f.periodo, d.nivel1
```

{% table data="pnl_layout" /%}

## Cuentas P&L sin Mapeo

```sql cuentas_sin_mapeo
select
    f.empresa,
    f.cuenta_codigo,
    f.cuenta_nombre,
    sum(coalesce(f.haber_ml, 0) - coalesce(f.debe_ml, 0)) as monto_ml
from postgres_finanzas_fact_libro_diario f
left join postgres_finanzas_dim_cuenta_pnl d
    on f.cuenta_codigo = d.cuenta_codigo
where f.es_pnl = true and d.cuenta_codigo is null
group by f.empresa, f.cuenta_codigo, f.cuenta_nombre
order by abs(sum(coalesce(f.haber_ml, 0) - coalesce(f.debe_ml, 0))) desc
```

{% table data="cuentas_sin_mapeo" /%}


{% table data="resumen_mes" /%}