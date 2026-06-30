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
    select m.empresa, cast(null as Nullable(String)) as oficina, m.periodo,
        m.cuenta_codigo, m.saldo_ml,
        coalesce(mt.nivel1, 'SIN MAPEO') as nivel1,
        coalesce(mt.is_fallback, true) as is_fallback
    from movimientos_pnl m
    left join matches mt on mt.id = m.id and mt.rn = 1
)

select empresa, oficina, periodo,
    sum(case when nivel1 = 'Ingresos' then saldo_ml else 0 end) as ingresos_ml,
    sum(case when nivel1 <> 'Ingresos' then saldo_ml else 0 end) as gastos_ml,
    sum(saldo_ml) as resultado_ml,
    count(distinct case when is_fallback = true or nivel1 in ('SIN MAPEO','P&L sin clasificar') then cuenta_codigo end) as cuentas_revision
from base
where periodo = (select max(periodo) from base)
group by empresa, oficina, periodo
order by empresa, periodo