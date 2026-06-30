---
title: EERR Finanzas
queries:
  - cargas: cargas.sql
  - pnl_nivel1: pnl/pnl_nivel1.sql
  - pnl_estructurado: pnl/pnl_estructurado.sql
  - resultado_mensual: pnl/resultado_mensual.sql
  - cuentas_revision: pnl/cuentas_revision.sql
---

# EERR Finanzas

Primera versión de reportería financiera con Neon Postgres + Evidence.

## Últimas cargas

{% table data="cargas" /%}

## Resultado mensual

{% table data="resultado_mensual" /%}

## PNL por Nivel 1

{% table data="pnl_nivel1" /%}

## PNL estructurado

{% table data="pnl_estructurado" /%}

## Cuentas por revisar

Estas cuentas están siendo procesadas por fallback o quedaron sin clasificación específica. La idea es ir agregando reglas exactas en `etl/config/pnl_mapping_rules.json`.

{% table data="cuentas_revision" /%}
