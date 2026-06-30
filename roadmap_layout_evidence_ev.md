# Roadmap de implementación de layout Engel & Völkers en Evidence

## Contexto

Este roadmap parte desde la **Fase 1**, asumiendo que ya están resueltos los puntos previos de configuración mínima:

- `evidence.config.yaml` válido.
- `access.yaml` creado.
- Evidence Team conectado al repo.
- Proyecto Evidence ubicado en `/evidence`.
- Monorepo con `/etl` y `/evidence`.
- Fuente Evidence configurada como `postgres_finanzas`.

El objetivo es adaptar la reportería financiera a un look & feel Engel & Völkers: premium, sobrio, editorial, con mucho espacio en blanco, gris oscuro como color base, rojo como acento controlado y formato financiero claro.

---

# Fase 1 — Sistema visual base

## Objetivo

Crear una capa centralizada de diseño para que colores, tipografías, espaciados y estilos base no queden hardcodeados en cada página o componente.

## 1.1 Crear archivo de tokens visuales

Crear una capa de estilos/tokens en Evidence. Opencode debe revisar la estructura actual del proyecto y elegir la opción compatible con la versión usada.

Opciones posibles:

```text
evidence/components/EVTheme.svelte
```

o, si el proyecto soporta CSS global:

```text
evidence/static/ev-theme.css
```

## 1.2 Tokens mínimos

```css
:root {
  --ev-white: #ffffff;
  --ev-black: #303030;
  --ev-gray-1: #282626;
  --ev-gray-2: #404040;
  --ev-gray-3: #666666;
  --ev-gray-6: #b3b3b3;
  --ev-gray-7: #cccccc;
  --ev-beige-1: #e2d9d0;
  --ev-beige-2: #f8f5f0;
  --ev-red: #e60000;
  --ev-dark-red: #910f05;

  --ev-bg: #ffffff;
  --ev-surface: #f8f5f0;
  --ev-border: #e2d9d0;
  --ev-text: #303030;
  --ev-text-muted: #666666;
  --ev-negative: #e60000;
  --ev-positive: #303030;

  --ev-font-head: Georgia, "Times New Roman", serif;
  --ev-font-text: Arial, Helvetica, sans-serif;

  --ev-radius: 0px;
  --ev-space-xs: 4px;
  --ev-space-sm: 8px;
  --ev-space-md: 16px;
  --ev-space-lg: 24px;
  --ev-space-xl: 40px;
  --ev-space-xxl: 64px;
}
```

## 1.3 Reglas visuales base

- Fondo dominante blanco.
- Texto principal en gris oscuro.
- Rojo usado solo como acento discreto.
- Beige claro para superficies suaves.
- Espacio en blanco generoso.
- Estética sobria, limpia y editorial.
- Evitar fondos rojos o grandes masas de color.
- Evitar colores fuera de la paleta.

## Acceptance criteria

```text
- Existe un único lugar para modificar colores, tipografías y spacing.
- No hay colores hardcodeados repetidos en páginas.
- El rojo se usa solo para acentos, warnings y negativos financieros.
- El reporte se siente más editorial y menos dashboard genérico.
```

---

# Fase 2 — Componentes reutilizables

## Objetivo

Crear componentes propios para reportería financiera, evitando repetir lógica de formato en cada página.

---

## 2.1 Componente `Money.svelte`

Crear:

```text
evidence/components/Money.svelte
```

### Responsabilidad

- Recibir un valor numérico.
- Formatearlo como CLP.
- Sin decimales.
- Separador de miles chileno.
- Negativos en rojo.
- Negativos entre paréntesis.
- Alineación a la derecha.
- Mantener formato tabular para lectura financiera.

### Formato esperado

```text
$ 124.241.972
($ 51.310.670)
```

### Pseudológica

```js
const raw = Number(value ?? 0);
const abs = Math.abs(raw);

const formatted = new Intl.NumberFormat("es-CL", {
  style: "currency",
  currency: "CLP",
  maximumFractionDigits: 0
}).format(abs);

const display = raw < 0 ? `(${formatted})` : formatted;
```

### CSS esperado

```css
.money {
  font-variant-numeric: tabular-nums;
  text-align: right;
  white-space: nowrap;
}

.money.negative {
  color: var(--ev-negative);
  font-weight: 600;
}
```

### Acceptance criteria

```text
- Todos los montos negativos aparecen en rojo.
- Todos los montos CLP aparecen sin decimales.
- Los negativos aparecen entre paréntesis.
- No se transforma el número a string en Neon.
- El componente puede reutilizarse en KPIs, tablas y cards.
```

---

## 2.2 Componente `EVKpiCard.svelte`

Crear:

```text
evidence/components/EVKpiCard.svelte
```

### Props sugeridas

```text
title
value
subtitle
variant: default | result | warning
```

### Uso esperado

- Ingresos.
- Gastos.
- Resultado.
- Cuentas por revisar.
- Última carga.

### Estilo esperado

- Fondo blanco o beige muy claro.
- Borde fino.
- Mucho espacio interno.
- Título en uppercase pequeño con tracking.
- Valor grande, limpio y legible.
- Rojo solo si `variant = warning` o si el valor es negativo.
- Sin sombras pesadas.
- Sin bordes redondeados excesivos.

### Acceptance criteria

```text
- La home tiene una fila de KPIs financieros.
- Las cards no usan rojo dominante.
- El resultado final se distingue sin romper la sobriedad visual.
```

---

## 2.3 Componente `EVSectionTitle.svelte`

Crear:

```text
evidence/components/EVSectionTitle.svelte
```

### Props sugeridas

```text
title
subtitle
```

### Uso esperado

Separar secciones como:

- Resumen ejecutivo.
- Resultado mensual.
- PNL por Nivel 1.
- PNL estructurado.
- Cuentas por revisar.

### Estilo esperado

- Título con serif fallback: Georgia.
- Subtítulo en sans serif: Arial.
- Línea roja corta como acento.
- La línea roja no debe ocupar todo el ancho.
- El componente debe reforzar jerarquía y aire visual.

### Acceptance criteria

```text
- Cada sección tiene jerarquía clara.
- La línea roja se usa como acento organizacional, no como borde decorativo excesivo.
- El layout respeta espacio en blanco generoso.
```

---

## 2.4 Componente `EVFinancialTable.svelte`

Crear:

```text
evidence/components/EVFinancialTable.svelte
```

### Responsabilidad

Renderizar tablas financieras con formato más cercano a un estado de resultados.

### Funcionalidad mínima

- Recibir dataset.
- Mostrar columnas de nivel financiero.
- Mostrar monto usando `Money.svelte`.
- Alinear montos a la derecha.
- Resaltar subtotales o resultados.
- Marcar cuentas/filas que requieren revisión.
- Aplicar negativos en rojo.
- Permitir que el PNL se lea como reporte financiero, no como tabla cruda.

### Props sugeridas

```text
data
labelColumn
amountColumn
levelColumns
highlightRows
```

Para el MVP puede ser específico para `pnl_estructurado`.

### Acceptance criteria

```text
- PNL estructurado se ve como estado financiero.
- Montos alineados a la derecha.
- Montos negativos en rojo.
- Filas de resultado o subtotales destacadas.
- Fallbacks o cuentas por revisar visibles, pero sin dominar visualmente.
```

---

# Fase 3 — Queries de presentación

## Objetivo

Mantener el SQL pesado fuera de `pages/index.md` y crear queries reutilizables en `/evidence/queries`.

---

## 3.1 Crear query `pnl_resumen_kpis.sql`

Crear:

```text
evidence/queries/pnl/pnl_resumen_kpis.sql
```

Debe devolver, al menos:

```text
empresa
oficina
periodo
ingresos_ml
gastos_ml
resultado_ml
cuentas_revision
```

### Lógica esperada

- Basarse en `resultado_mensual.sql`.
- Integrar conteo de cuentas por revisar desde `cuentas_revision.sql`.
- Mantener valores numéricos, no strings formateados.

### Acceptance criteria

```text
- La home puede mostrar KPIs sin recalcular lógica en el markdown.
- Los datos se mantienen numéricos.
- La query puede reutilizarse en otras páginas.
```

---

## 3.2 Ajustar `pnl_estructurado.sql`

Agregar columnas de control visual:

```sql
case
  when nivel1 in ('Resultado Final', 'EBITDA', 'Resultado')
    or nivel2 in ('Resultado Final', 'EBITDA', 'Resultado')
  then true
  else false
end as es_subtotal,

case
  when contiene_fallback then true
  else false
end as requiere_revision
```

Si todavía no existen líneas reales de subtotal, marcar por ahora:

```text
P&L sin clasificar
Cuentas fallback
```

### Acceptance criteria

```text
- La tabla sabe qué filas destacar.
- La tabla sabe qué filas requieren revisión.
- La lógica visual se controla desde queries, no desde condicionales dispersos en componentes.
```

---

## 3.3 Revisar queries existentes

Mantener esta estructura:

```text
evidence/queries/
  cargas.sql
  pnl/
    pnl_movimientos_mapeados.sql
    pnl_nivel1.sql
    pnl_estructurado.sql
    resultado_mensual.sql
    cuentas_revision.sql
    pnl_resumen_kpis.sql
```

### Acceptance criteria

```text
- No hay CTEs largos dentro de pages/index.md.
- Las queries son reutilizables.
- Los nombres son claros y consistentes.
```

---

# Fase 4 — Rediseñar `pages/index.md`

## Objetivo

Convertir `index.md` en una página de presentación, no en un archivo con lógica pesada.

## 4.1 Estructura recomendada

```markdown
---
title: EERR Finanzas
queries:
  - cargas: cargas.sql
  - pnl_resumen_kpis: pnl/pnl_resumen_kpis.sql
  - pnl_nivel1: pnl/pnl_nivel1.sql
  - pnl_estructurado: pnl/pnl_estructurado.sql
  - resultado_mensual: pnl/resultado_mensual.sql
  - cuentas_revision: pnl/cuentas_revision.sql
---

<script>
  import EVSectionTitle from '../components/EVSectionTitle.svelte';
  import EVKpiCard from '../components/EVKpiCard.svelte';
  import EVFinancialTable from '../components/EVFinancialTable.svelte';
</script>

# EERR Finanzas

Reporte financiero mensual conectado a Neon Postgres.

<EVSectionTitle
  title="Resumen ejecutivo"
  subtitle="Indicadores principales del periodo"
/>

<!-- KPIs -->

<EVSectionTitle
  title="Resultado mensual"
  subtitle="Evolución de ingresos, gastos y resultado"
/>

{% table data="resultado_mensual" /%}

<EVSectionTitle
  title="PNL estructurado"
  subtitle="Agrupación por niveles financieros"
/>

<EVFinancialTable data={pnl_estructurado} />

<EVSectionTitle
  title="Cuentas por revisar"
  subtitle="Cuentas procesadas por fallback o sin regla exacta"
/>

{% table data="cuentas_revision" /%}
```

## 4.2 Reglas

- El markdown debe ser legible.
- No poner SQL inline salvo consultas muy pequeñas de depuración.
- Los componentes deben recibir datasets ya preparados.
- La estructura visual debe ser clara: resumen, PNL, revisión.

## Acceptance criteria

```text
- index.md es fácil de leer.
- La lógica pesada vive en /queries.
- El layout visual vive en componentes.
- La página inicial se siente como reporte ejecutivo financiero.
```

---

# Fase 5 — Branding de tablas y formato financiero

## Objetivo

Hacer que las tablas y montos se vean financieros, sobrios y consistentes.

---

## 5.1 Tablas

Estilo esperado:

```text
- Header gris/beige claro.
- Texto gris oscuro.
- Bordes finos.
- Filas con buena altura.
- Sin exceso de color.
- Montos tabulares.
- Alineación derecha para montos.
- Texto alineado a la izquierda.
```

## 5.2 Negativos

Regla:

```text
- Negativos financieros en rojo #E60000.
- No usar rojo para toda una fila salvo casos de warning.
- El rojo debe ser acento contenido.
- Preferir negativos entre paréntesis.
```

## 5.3 Fallback / revisión

Cuentas fallback:

```text
- Badge discreto: “Revisar”.
- Color rojo oscuro o borde rojo.
- Evitar fondos rojos dominantes.
- Mostrar siempre cuentas con fallback en sección separada.
```

## 5.4 Formato de moneda

Regla global:

```text
- CLP.
- Sin decimales.
- Separador de miles es-CL.
- Negativos en rojo.
- Negativos entre paréntesis.
```

Ejemplo:

```text
$ 124.241.972
($ 51.310.670)
```

## Acceptance criteria

```text
- El rojo no domina la pantalla.
- Los negativos son evidentes.
- Las cuentas por revisar son visibles sin romper el look premium.
- Los números se leen como reporte financiero profesional.
```

---

# Fase 6 — Validación local

## Objetivo

Validar que todo compile localmente antes de hacer push.

Desde:

```powershell
cd evidence
```

Ejecutar:

```powershell
npm run sources
npm run build
npm run dev
```

Si existe script strict:

```powershell
npm run build:strict
```

## Checklist local

```text
- npm run sources pasa.
- npm run build pasa.
- npm run dev muestra la home.
- No hay errores de imports Svelte.
- No hay errores YAML.
- No hay errores por queries inexistentes.
- No hay credenciales en archivos versionados.
- Montos negativos aparecen en rojo.
- Montos aparecen como CLP.
```

---

# Fase 7 — GitHub / Evidence Team

## Objetivo

Publicar el cambio de forma controlada.

Desde la raíz del repo:

```powershell
git status
git add .
git commit -m "Implementa layout financiero Engel Volkers"
git push origin main
```

## Validación en Evidence Team

Revisar:

```text
- Project root = evidence.
- Data source postgres_finanzas configurado.
- access.yaml existe.
- evidence.config.yaml válido.
- Publish exitoso.
- La última versión publicada muestra layout nuevo.
- Si falla build, viewers siguen viendo versión anterior.
```

## Recomendación de branch

Para cambios visuales relevantes, trabajar en branch:

```text
feature/ev-layout
```

Flujo:

```powershell
git checkout -b feature/ev-layout
git add .
git commit -m "Implementa layout financiero EV"
git push origin feature/ev-layout
```

Luego abrir Pull Request y revisar preview antes de mergear a `main`.

---

# Prompt corto para Opencode

```text
Implementa un layout financiero Engel & Völkers en el monorepo finanzas-evidence.

Contexto:
- Evidence vive en /evidence.
- ETL vive en /etl.
- Evidence Team usa Project root = evidence.
- No tocar credenciales ni .env.
- No subir archivos xls/xlsx/csv.
- Fuente Evidence: postgres_finanzas.
- Tablas disponibles:
  - postgres_finanzas_fact_libro_diario
  - postgres_finanzas_cargas_libro_diario
  - postgres_finanzas_dim_pnl_mapping_rule

Objetivo:
1. Crear sistema visual Engel & Völkers:
   - fondo blanco
   - texto #303030
   - rojo #E60000 solo como acento
   - beige #F8F5F0 para superficies suaves
   - tipografías fallback Georgia para titulares y Arial para UI/cuerpo.
2. Crear componentes reutilizables:
   - Money.svelte: CLP sin decimales, miles es-CL, negativos rojos y entre paréntesis.
   - EVKpiCard.svelte.
   - EVSectionTitle.svelte.
   - EVFinancialTable.svelte.
3. Mantener SQL pesado en /evidence/queries, no en pages/index.md.
4. Crear query pnl/pnl_resumen_kpis.sql.
5. Ajustar index.md para mostrar:
   - resumen ejecutivo
   - KPIs
   - resultado mensual
   - PNL por nivel 1
   - PNL estructurado
   - cuentas por revisar
6. Validar con:
   - npm run sources
   - npm run build
   - npm run dev

Criterios:
- Montos siempre numéricos en queries.
- Formato moneda solo en capa visual.
- Negativos en rojo.
- PNL debe verse como reporte financiero premium, no tabla cruda.
- No usar rojo como color dominante.
- No romper publish en Evidence Team.
```
