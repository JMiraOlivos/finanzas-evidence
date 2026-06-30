---
title: EERR Finanzas
---

# EERR Finanzas

Engel & Völkers Finanzas. Reporte financiero mensual conectado a Neon Postgres, con lectura ejecutiva de ingresos, gastos, resultado y cuentas pendientes de clasificacion.

{% callout %}
Los montos se mantienen numericos en las queries. El formato financiero se aplica en componentes Evidence con formato CLP visual, negativos en rojo y tablas de lectura ejecutiva.
{% /callout %}

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

```sql pnl_resumen_kpis
with movimientos_pnl as (
    select
        f.id,
        f.empresa,
        f.periodo,
        f.cuenta_codigo,
        f.saldo_ml
    from postgres_finanzas_fact_libro_diario f
    where left(cast(f.cuenta_codigo as varchar), 1) in ('4', '5', '6')
),
matches as (
    select m.id, r.nivel1, r.is_fallback,
        row_number() over (
            partition by m.id
            order by coalesce(r.priority, -999999) desc,
                     length(coalesce(r.pattern, '')) desc,
                     coalesce(r.orden, 9999) asc,
                     coalesce(r.id, 999999999) asc
        ) as rn
    from movimientos_pnl m
    join postgres_finanzas_dim_pnl_mapping_rule r on r.activa = true
    where (r.rule_type = 'exact'  and r.pattern = m.cuenta_codigo)
       or (r.rule_type = 'prefix' and left(m.cuenta_codigo, length(r.pattern)) = r.pattern)
       or (r.rule_type = 'default')
),
base as (
    select m.empresa, m.periodo,
        m.cuenta_codigo, m.saldo_ml,
        coalesce(mt.nivel1, 'SIN MAPEO') as nivel1,
        coalesce(mt.is_fallback, true) as is_fallback
    from movimientos_pnl m
    left join matches mt on mt.id = m.id and mt.rn = 1
)
select empresa,
    sum(case when nivel1 = 'Ingresos' then saldo_ml else 0 end) as ingresos_ml,
    sum(case when nivel1 <> 'Ingresos' then saldo_ml else 0 end) as gastos_ml,
    sum(saldo_ml) as resultado_ml,
    count(distinct case when is_fallback = true or nivel1 in ('SIN MAPEO','P&L sin clasificar') then cuenta_codigo end) as cuentas_revision
from base
group by empresa
order by empresa
```

```sql resultado_mensual
with movimientos_pnl as (
    select f.id, f.empresa, f.periodo, f.cuenta_codigo, f.saldo_ml
    from postgres_finanzas_fact_libro_diario f
    where left(cast(f.cuenta_codigo as varchar), 1) in ('4', '5', '6')
),
matches as (
    select m.id, r.nivel1,
        row_number() over (
            partition by m.id
            order by coalesce(r.priority, -999999) desc,
                     length(coalesce(r.pattern, '')) desc,
                     coalesce(r.orden, 9999) asc,
                     coalesce(r.id, 999999999) asc
        ) as rn
    from movimientos_pnl m
    join postgres_finanzas_dim_pnl_mapping_rule r on r.activa = true
    where (r.rule_type = 'exact'  and r.pattern = m.cuenta_codigo)
       or (r.rule_type = 'prefix' and left(m.cuenta_codigo, length(r.pattern)) = r.pattern)
       or (r.rule_type = 'default')
),
base as (
    select m.empresa, m.periodo, m.saldo_ml,
        coalesce(mt.nivel1, 'SIN MAPEO') as nivel1
    from movimientos_pnl m
    left join matches mt on mt.id = m.id and mt.rn = 1
)
select empresa, periodo,
    sum(case when nivel1 = 'Ingresos' then saldo_ml else 0 end) as ingresos_ml,
    sum(case when nivel1 <> 'Ingresos' then saldo_ml else 0 end) as gastos_ml,
    sum(saldo_ml) as resultado_ml
from base
group by empresa, periodo
order by empresa, periodo
```

```sql pnl_nivel1
with movimientos_pnl as (
    select f.id, f.empresa, f.periodo, f.cuenta_codigo, f.saldo_ml
    from postgres_finanzas_fact_libro_diario f
    where left(cast(f.cuenta_codigo as varchar), 1) in ('4', '5', '6')
),
matches as (
    select m.id, r.orden, r.nivel1,
        row_number() over (
            partition by m.id
            order by coalesce(r.priority, -999999) desc,
                     length(coalesce(r.pattern, '')) desc,
                     coalesce(r.orden, 9999) asc,
                     coalesce(r.id, 999999999) asc
        ) as rn
    from movimientos_pnl m
    join postgres_finanzas_dim_pnl_mapping_rule r on r.activa = true
    where (r.rule_type = 'exact'  and r.pattern = m.cuenta_codigo)
       or (r.rule_type = 'prefix' and left(m.cuenta_codigo, length(r.pattern)) = r.pattern)
       or (r.rule_type = 'default')
),
base as (
    select m.empresa, m.periodo,
        coalesce(mt.orden, 9999) as orden,
        coalesce(mt.nivel1, 'SIN MAPEO') as nivel1,
        m.saldo_ml
    from movimientos_pnl m
    left join matches mt on mt.id = m.id and mt.rn = 1
)
select empresa, periodo, orden, nivel1,
    sum(saldo_ml) as monto_ml,
    count(*) as movimientos
from base
group by empresa, periodo, orden, nivel1
order by empresa, periodo, orden, nivel1
```

```sql pnl_estructurado
with movimientos_pnl as (
    select f.id, f.empresa, f.periodo, f.cuenta_codigo, f.saldo_ml
    from postgres_finanzas_fact_libro_diario f
    where left(cast(f.cuenta_codigo as varchar), 1) in ('4', '5', '6')
),
matches as (
    select m.id, r.orden, r.nivel1, r.nivel2, r.nivel3, r.is_fallback,
        row_number() over (
            partition by m.id
            order by coalesce(r.priority, -999999) desc,
                     length(coalesce(r.pattern, '')) desc,
                     coalesce(r.orden, 9999) asc,
                     coalesce(r.id, 999999999) asc
        ) as rn
    from movimientos_pnl m
    join postgres_finanzas_dim_pnl_mapping_rule r on r.activa = true
    where (r.rule_type = 'exact'  and r.pattern = m.cuenta_codigo)
       or (r.rule_type = 'prefix' and left(m.cuenta_codigo, length(r.pattern)) = r.pattern)
       or (r.rule_type = 'default')
),
base as (
    select m.empresa, m.periodo,
        coalesce(mt.orden, 9999) as orden,
        coalesce(mt.nivel1, 'SIN MAPEO') as nivel1,
        coalesce(mt.nivel2, 'SIN MAPEO') as nivel2,
        coalesce(mt.nivel3, 'SIN MAPEO') as nivel3,
        coalesce(mt.is_fallback, true) as is_fallback,
        m.saldo_ml
    from movimientos_pnl m
    left join matches mt on mt.id = m.id and mt.rn = 1
),
layout as (
    select 1 as pnl_sort, 'Ingresos' as pnl_section, 1 as calc_type, 1 as detail, '' as indexsect, 'Ingresos' as pnl_layout
    union all select 2, 'Gastos Variables', 1, 1, '', 'Gastos Variables'
    union all select 3, 'RRHH', 1, 1, '', 'RRHH'
    union all select 4, 'Marketing', 1, 1, '', 'Marketing'
    union all select 5, 'Gastos Administración', 1, 1, '', 'Gastos Administración'
    union all select 6, 'Asesorías', 1, 1, '', 'Asesorías'
    union all select 7, 'Gastos Oficina/Ocupación', 1, 1, '', 'Gastos Oficina/Ocupación'
    union all select 8, 'Tecnología', 1, 1, '', 'Tecnología'
    union all select 9, 'No Operacionales', 1, 1, '', 'No Operacionales'
    union all select 12, 'Intereses, Impuestos, Depr. Y Amort', 1, 1, '', 'Intereses, Impuestos, Depr. Y Amort'
    union all select 15, 'Impuesto', 1, 1, '', 'Impuesto'
),
detalle as (
    select
        b.empresa,
        l.pnl_sort,
        l.pnl_section,
        l.calc_type,
        l.detail,
        l.indexsect,
        l.pnl_layout,
        b.nivel2,
        b.nivel3,
        sum(b.saldo_ml) as monto_ml,
        count(*) as movimientos,
        max(b.is_fallback) as contiene_fallback,
        case
            when max(b.is_fallback) = true
              or b.nivel1 in ('P&L sin clasificar', 'SIN MAPEO')
              or b.nivel2 in ('P&L sin clasificar', 'SIN MAPEO')
              or b.nivel3 in ('P&L sin clasificar', 'SIN MAPEO')
            then true else false
        end as requiere_revision
    from base b
    inner join layout l on b.nivel1 = l.pnl_layout
    group by b.empresa, l.pnl_sort, l.pnl_section, l.calc_type, l.detail, l.indexsect, l.pnl_layout, b.nivel2, b.nivel3, b.nivel1
),
totales_seccion as (
    select
        empresa,
        pnl_sort,
        sum(monto_ml) as monto_ml,
        sum(movimientos) as movimientos
    from detalle
    group by empresa, pnl_sort
),
calculados as (
    select
        empresa,
        11 as pnl_sort,
        'EBITDA' as pnl_section,
        2 as calc_type,
        0 as detail,
        '' as indexsect,
        'EBITDA' as pnl_layout,
        '' as nivel2,
        '' as nivel3,
        sum(case when pnl_sort between 1 and 9 then monto_ml else 0 end) as monto_ml,
        sum(case when pnl_sort between 1 and 9 then movimientos else 0 end) as movimientos,
        false as contiene_fallback,
        false as requiere_revision
    from totales_seccion
    group by empresa
    union all
    select
        empresa,
        14 as pnl_sort,
        'Resultado Antes Imp.' as pnl_section,
        2 as calc_type,
        0 as detail,
        '' as indexsect,
        'Resultado Antes Imp.' as pnl_layout,
        '' as nivel2,
        '' as nivel3,
        sum(case when pnl_sort between 1 and 9 or pnl_sort = 12 then monto_ml else 0 end) as monto_ml,
        sum(case when pnl_sort between 1 and 9 or pnl_sort = 12 then movimientos else 0 end) as movimientos,
        false as contiene_fallback,
        false as requiere_revision
    from totales_seccion
    group by empresa
    union all
    select
        empresa,
        17 as pnl_sort,
        'Resultado Final' as pnl_section,
        2 as calc_type,
        0 as detail,
        '' as indexsect,
        'Resultado Final' as pnl_layout,
        '' as nivel2,
        '' as nivel3,
        sum(case when pnl_sort between 1 and 9 or pnl_sort in (12, 15) then monto_ml else 0 end) as monto_ml,
        sum(case when pnl_sort between 1 and 9 or pnl_sort in (12, 15) then movimientos else 0 end) as movimientos,
        false as contiene_fallback,
        false as requiere_revision
    from totales_seccion
    group by empresa
),
pnl_final as (
    select * from detalle
    union all
    select * from calculados
)
select
    *,
    abs(monto_ml) as sort_abs
from pnl_final
order by empresa, pnl_sort, sort_abs desc, nivel2, nivel3
```

```sql cuentas_revision
with movimientos_pnl as (
    select f.id, f.empresa, f.periodo, f.cuenta_codigo, f.cuenta_nombre, f.saldo_ml
    from postgres_finanzas_fact_libro_diario f
    where left(cast(f.cuenta_codigo as varchar), 1) in ('4', '5', '6')
),
matches as (
    select m.id, r.rule_key, r.rule_type, r.nivel1, r.nivel2, r.nivel3, r.is_fallback,
        row_number() over (
            partition by m.id
            order by coalesce(r.priority, -999999) desc,
                     length(coalesce(r.pattern, '')) desc,
                     coalesce(r.orden, 9999) asc,
                     coalesce(r.id, 999999999) asc
        ) as rn
    from movimientos_pnl m
    join postgres_finanzas_dim_pnl_mapping_rule r on r.activa = true
    where (r.rule_type = 'exact'  and r.pattern = m.cuenta_codigo)
       or (r.rule_type = 'prefix' and left(m.cuenta_codigo, length(r.pattern)) = r.pattern)
       or (r.rule_type = 'default')
),
base as (
    select m.empresa, m.cuenta_codigo, m.cuenta_nombre, m.saldo_ml,
        coalesce(mt.rule_key, 'sin_regla') as rule_key,
        coalesce(mt.rule_type, 'none') as rule_type,
        coalesce(mt.nivel1, 'SIN MAPEO') as nivel1,
        coalesce(mt.nivel2, 'SIN MAPEO') as nivel2,
        coalesce(mt.nivel3, 'SIN MAPEO') as nivel3,
        coalesce(mt.is_fallback, true) as is_fallback
    from movimientos_pnl m
    left join matches mt on mt.id = m.id and mt.rn = 1
),
filtrado as (
    select * from base
    where is_fallback = true
       or nivel1 in ('SIN MAPEO', 'P&L sin clasificar')
)
select empresa, cuenta_codigo,
    any_value(cuenta_nombre) as cuenta_nombre,
    any_value(rule_key) as regla_aplicada,
    any_value(rule_type) as tipo_regla,
    any_value(nivel1) as nivel1,
    any_value(nivel2) as nivel2,
    any_value(nivel3) as nivel3,
    sum(saldo_ml) as monto_ml,
    count(*) as movimientos
from filtrado
group by empresa, cuenta_codigo
order by abs(sum(saldo_ml)) desc
```

## Resumen ejecutivo

Indicadores acumulados para todos los periodos disponibles.

{% big_value
    data="pnl_resumen_kpis"
    value="sum(ingresos_ml)"
    title="Ingresos"
    fmt="usd0"
    text_size="3xl"
/%}
{% big_value
    data="pnl_resumen_kpis"
    value="sum(gastos_ml)"
    title="Gastos"
    fmt="usd0"
    text_size="3xl"
/%}
{% big_value
    data="pnl_resumen_kpis"
    value="sum(resultado_ml)"
    title="Resultado"
    fmt="usd0"
    text_size="3xl"
/%}
{% big_value
    data="pnl_resumen_kpis"
    value="sum(cuentas_revision)"
    title="Cuentas por revisar"
    fmt="num0"
    text_size="3xl"
/%}

## Ultimas cargas

Control operativo de las cargas mas recientes del libro diario.

{% table
    data="cargas"
    limit=5
    row_lines=true
    row_shading=false
    wrap=true
%}
    {% dimension value="id" title="ID" /%}
    {% dimension value="empresa_id" title="Empresa" /%}
    {% dimension value="archivo_nombre" title="Archivo" /%}
    {% dimension value="fecha_min" title="Fecha min" date_grain="day" /%}
    {% dimension value="fecha_max" title="Fecha max" date_grain="day" /%}
    {% measure value="sum(filas_leidas)" title="Filas leidas" fmt="num0" align="right" /%}
    {% measure value="sum(filas_insertadas)" title="Filas insertadas" fmt="num0" align="right" /%}
    {% measure value="sum(saldo_ml)" title="Saldo" fmt="usd0" red_negatives=true align="right" /%}
{% /table %}

## Resultado mensual

Evolucion de ingresos, gastos y resultado por empresa y periodo.

{% table
    data="resultado_mensual"
    row_lines=true
    row_shading=false
    repeat_values=true
%}
    {% dimension value="empresa" title="Empresa" /%}
    {% dimension value="periodo" title="Periodo" /%}
    {% measure value="sum(ingresos_ml)" title="Ingresos" fmt="usd0" red_negatives=true align="right" /%}
    {% measure value="sum(gastos_ml)" title="Gastos" fmt="usd0" red_negatives=true align="right" /%}
    {% measure value="sum(resultado_ml)" title="Resultado" fmt="usd0" red_negatives=true align="right" /%}
{% /table %}

## PNL por nivel 1

Vista agregada por primera jerarquia financiera para identificar rapidamente la composicion del resultado.

{% table
    data="pnl_nivel1"
    row_lines=true
    row_shading=false
    repeat_values=true
    subtotals=true
    subtotal_position="top"
    total_label="Resultado"
%}
    {% dimension value="empresa" title="Empresa" /%}
    {% dimension value="periodo" title="Periodo" /%}
    {% dimension value="nivel1" title="Nivel 1" /%}
    {% measure value="sum(movimientos)" title="Movimientos" fmt="num0" align="right" /%}
    {% measure value="sum(monto_ml)" title="Monto" fmt="usd0" red_negatives=true align="right" /%}
{% /table %}

## PNL estructurado

Estado de resultados con niveles financieros, subtotales y alertas discretas para partidas que requieren revision.

{% table
    data="pnl_estructurado"
    row_lines=true
    row_shading=false
    repeat_values=false
    subtotals=false
    total_label="Resultado"
    row_conditional_colors="case when max(calc_type) = 2 or max(requiere_revision) then '#F8F5F0' else null end"
%}
    {% dimension value="pnl_sort" title="Sort" sort="asc" hide=true /%}
    {% dimension value="sort_abs" title="Sort Abs" sort="desc" hide=true /%}
    {% dimension value="calc_type" title="Calc Type" hide=true /%}
    {% dimension value="pnl_section" title="PNL Section" /%}
    {% dimension value="nivel2" title="Nivel 2" /%}
    {% dimension value="nivel3" title="Nivel 3" /%}
    {% pivot value="empresa" title="Empresa" /%}
    {% measure value="sum(monto_ml)" title="Monto" fmt="usd0" red_negatives=true align="right" /%}
{% /table %}

## Cuentas por revisar

Cuentas procesadas por fallback o sin regla exacta. El objetivo es depurarlas en `etl/config/pnl_mapping_rules.json`.

{% table
    data="cuentas_revision"
    row_lines=true
    row_shading=false
    repeat_values=true
    search=true
    row_conditional_colors="'#F8F5F0'"
%}
    {% dimension value="empresa" title="Empresa" /%}
    {% dimension value="cuenta_codigo" title="Cuenta" /%}
    {% dimension value="cuenta_nombre" title="Nombre" /%}
    {% dimension value="regla_aplicada" title="Regla" /%}
    {% dimension value="tipo_regla" title="Tipo" /%}
    {% dimension value="nivel1" title="Nivel 1" /%}
    {% dimension value="nivel2" title="Nivel 2" /%}
    {% dimension value="nivel3" title="Nivel 3" /%}
    {% measure value="sum(movimientos)" title="Movimientos" fmt="num0" align="right" /%}
    {% measure value="sum(monto_ml)" title="Monto" fmt="usd0" red_negatives=true align="right" /%}
{% /table %}
