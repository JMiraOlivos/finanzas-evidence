---
title: EERR Finanzas
queries:
  - cargas: cargas.sql
  - pnl_resumen_kpis: pnl/pnl_resumen_kpis.sql
  - resultado_mensual: pnl/resultado_mensual.sql
  - pnl_nivel1: pnl/pnl_nivel1.sql
  - pnl_estructurado: pnl/pnl_estructurado.sql
  - cuentas_revision: pnl/cuentas_revision.sql
---

# EERR Finanzas

Engel & Völkers Finanzas. Reporte financiero mensual conectado a Neon Postgres, con lectura ejecutiva de ingresos, gastos, resultado y cuentas pendientes de clasificacion.

{% callout %}
Los montos se mantienen numericos en las queries. El formato financiero se aplica en componentes Evidence con formato CLP visual, negativos en rojo y tablas de lectura ejecutiva.
{% /callout %}

## Resumen ejecutivo

Indicadores principales del ultimo periodo disponible.

{% row %}
    {% big_value
        data="pnl_resumen_kpis"
        value="sum(ingresos_ml)"
        title="Ingresos"
        fmt="$ #,##0;($ #,##0)"
        text_size="3xl"
    /%}
    {% big_value
        data="pnl_resumen_kpis"
        value="sum(gastos_ml)"
        title="Gastos"
        fmt="$ #,##0;($ #,##0)"
        text_size="3xl"
    /%}
    {% big_value
        data="pnl_resumen_kpis"
        value="sum(resultado_ml)"
        title="Resultado"
        fmt="$ #,##0;($ #,##0)"
        text_size="3xl"
    /%}
    {% big_value
        data="pnl_resumen_kpis"
        value="sum(cuentas_revision)"
        title="Cuentas por revisar"
        fmt="num0"
        text_size="3xl"
    /%}
{% /row %}

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
    {% dimension value="fecha_min" title="Fecha min" /%}
    {% dimension value="fecha_max" title="Fecha max" /%}
    {% measure value="sum(filas_leidas)" title="Filas leidas" fmt="num0" align="right" /%}
    {% measure value="sum(filas_insertadas)" title="Filas insertadas" fmt="num0" align="right" /%}
    {% measure value="sum(saldo_ml)" title="Saldo" fmt="$ #,##0;($ #,##0)" red_negatives=true align="right" /%}
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
    {% measure value="sum(ingresos_ml)" title="Ingresos" fmt="$ #,##0;($ #,##0)" red_negatives=true align="right" /%}
    {% measure value="sum(gastos_ml)" title="Gastos" fmt="$ #,##0;($ #,##0)" red_negatives=true align="right" /%}
    {% measure value="sum(resultado_ml)" title="Resultado" fmt="$ #,##0;($ #,##0)" red_negatives=true align="right" /%}
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
    {% measure value="sum(monto_ml)" title="Monto" fmt="$ #,##0;($ #,##0)" red_negatives=true align="right" /%}
{% /table %}

## PNL estructurado

Estado de resultados con niveles financieros, subtotales y alertas discretas para partidas que requieren revision.

{% table
    data="pnl_estructurado"
    row_lines=true
    row_shading=false
    repeat_values=false
    subtotals=true
    collapsible=true
    collapsed=false
    subtotal_position="top"
    total_label="Resultado"
    row_conditional_colors="case when bool_or(requiere_revision) then '#F8F5F0' else null end"
%}
    {% dimension value="nivel1" title="Nivel 1" /%}
    {% dimension value="nivel2" title="Nivel 2" /%}
    {% dimension value="nivel3" title="Nivel 3" /%}
    {% dimension value="empresa" title="Empresa" /%}
    {% dimension value="periodo" title="Periodo" /%}
    {% measure value="sum(movimientos)" title="Movimientos" fmt="num0" align="right" /%}
    {% measure value="sum(monto_ml)" title="Monto" fmt="$ #,##0;($ #,##0)" red_negatives=true align="right" /%}
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
    {% measure value="sum(monto_ml)" title="Monto" fmt="$ #,##0;($ #,##0)" red_negatives=true align="right" /%}
{% /table %}
