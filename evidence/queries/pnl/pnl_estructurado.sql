with movimientos_pnl as (
    select
        f.id,
        f.empresa,
        f.periodo,
        f.fecha,
        f.cuenta_codigo,
        f.cuenta_nombre,
        f.cuenta_contable,
        f.glosa,
        f.debe_ml,
        f.haber_ml,
        f.saldo_ml
    from postgres_finanzas_fact_libro_diario f
    where left(cast(f.cuenta_codigo as varchar), 1) in ('4', '5', '6')
),

candidatos as (
    select
        m.*,
        r.id as rule_id,
        r.rule_key,
        r.rule_type,
        r.pattern,
        r.priority,
        r.orden,
        r.nivel1,
        r.nivel2,
        r.nivel3,
        r.is_fallback,
        row_number() over (
            partition by m.id
            order by
                coalesce(r.priority, -999999) desc,
                length(coalesce(r.pattern, '')) desc,
                coalesce(r.orden, 9999) asc,
                coalesce(r.id, 999999999) asc
        ) as rn
    from movimientos_pnl m
    left join postgres_finanzas_dim_pnl_mapping_rule r
        on r.activa = true
       and (
              (r.rule_type = 'exact' and r.pattern = m.cuenta_codigo)
           or (r.rule_type = 'prefix' and left(m.cuenta_codigo, length(r.pattern)) = r.pattern)
           or (r.rule_type = 'default')
       )
),

base as (
    select
        empresa,
        periodo,
        fecha,
        cuenta_codigo,
        cuenta_nombre,
        cuenta_contable,
        glosa,
        debe_ml,
        haber_ml,
        saldo_ml,
        coalesce(rule_id, -1) as rule_id,
        coalesce(rule_key, 'sin_regla') as rule_key,
        coalesce(rule_type, 'none') as rule_type,
        coalesce(pattern, '') as pattern,
        coalesce(priority, 0) as priority,
        coalesce(orden, 9999) as orden,
        coalesce(nivel1, 'SIN MAPEO') as nivel1,
        coalesce(nivel2, 'SIN MAPEO') as nivel2,
        coalesce(nivel3, 'SIN MAPEO') as nivel3,
        coalesce(is_fallback, true) as is_fallback
    from candidatos
    where rn = 1
)
select
    empresa,
    periodo,
    orden,
    nivel1,
    nivel2,
    nivel3,
    sum(saldo_ml) as monto_ml,
    count(*) as movimientos,
    bool_or(is_fallback) as contiene_fallback,
    case
        when nivel1 in ('Resultado Final', 'EBITDA', 'Resultado')
          or nivel2 in ('Resultado Final', 'EBITDA', 'Resultado')
          or nivel1 in ('P&L sin clasificar', 'SIN MAPEO')
          or nivel2 in ('P&L sin clasificar', 'SIN MAPEO')
        then true
        else false
    end as es_subtotal,
    case
        when bool_or(is_fallback) = true
          or nivel1 in ('P&L sin clasificar', 'SIN MAPEO')
          or nivel2 in ('P&L sin clasificar', 'SIN MAPEO')
          or nivel3 in ('P&L sin clasificar', 'SIN MAPEO')
        then true
        else false
    end as requiere_revision
from base
group by empresa, periodo, orden, nivel1, nivel2, nivel3
order by empresa, periodo, orden, nivel1, nivel2, nivel3
