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

<script>
  import EVTheme from '../components/EVTheme.svelte';
  import EVSectionTitle from '../components/EVSectionTitle.svelte';
  import EVKpiCard from '../components/EVKpiCard.svelte';
  import EVFinancialTable from '../components/EVFinancialTable.svelte';
  import Money from '../components/Money.svelte';

  const rowsOf = (input) => {
    if (Array.isArray(input)) return input;
    if (Array.isArray(input?.rows)) return input.rows;
    if (Array.isArray(input?.data)) return input.data;
    return [];
  };

  $: kpiRows = rowsOf(pnl_resumen_kpis);
  $: kpi = kpiRows[kpiRows.length - 1] ?? {};
  $: cargaRows = rowsOf(cargas);
  $: ultimaCarga = cargaRows[0] ?? {};
  $: resultadoRows = rowsOf(resultado_mensual);
</script>

<EVTheme>
  <header class="hero">
    <div class="eyebrow">Engel & Völkers Finanzas</div>
    <h1>EERR Finanzas</h1>
    <p>
      Reporte financiero mensual conectado a Neon Postgres, con lectura ejecutiva de ingresos,
      gastos, resultado y cuentas pendientes de clasificacion.
    </p>
  </header>

  <EVSectionTitle
    title="Resumen ejecutivo"
    subtitle="Indicadores principales del ultimo periodo disponible. Los montos permanecen numericos en las queries y se formatean como CLP solo en la capa visual."
  />

  <section class="kpi-grid">
    <EVKpiCard title="Ingresos" value={kpi.ingresos_ml} subtitle={kpi.periodo ? `Periodo ${kpi.periodo}` : 'Ultimo periodo disponible'} />
    <EVKpiCard title="Gastos" value={kpi.gastos_ml} subtitle={kpi.empresa ? `Empresa ${kpi.empresa}` : 'Consolidado por empresa'} />
    <EVKpiCard title="Resultado" value={kpi.resultado_ml} subtitle="Ingresos menos gastos P&L" variant="result" />
    <EVKpiCard title="Cuentas por revisar" value={kpi.cuentas_revision} subtitle="Fallback o sin clasificacion exacta" format="number" variant="warning" />
  </section>

  <section class="load-note">
    <div>
      <span class="note-label">Ultima carga</span>
      <strong>{ultimaCarga.archivo_nombre ?? 'Sin cargas registradas'}</strong>
    </div>
    <div>
      <span class="note-label">Rango</span>
      <strong>{ultimaCarga.fecha_min ?? '-'} / {ultimaCarga.fecha_max ?? '-'}</strong>
    </div>
    <div>
      <span class="note-label">Saldo carga</span>
      <strong><Money value={ultimaCarga.saldo_ml} /></strong>
    </div>
  </section>

  <EVSectionTitle
    title="Resultado mensual"
    subtitle="Evolucion de ingresos, gastos y resultado por empresa y periodo."
  />

  <div class="monthly-table">
    {#if resultadoRows.length}
      <table>
        <thead>
          <tr>
            <th>Empresa</th>
            <th>Periodo</th>
            <th class="amount">Ingresos</th>
            <th class="amount">Gastos</th>
            <th class="amount">Resultado</th>
          </tr>
        </thead>
        <tbody>
          {#each resultadoRows as row}
            <tr>
              <td>{row.empresa}</td>
              <td>{row.periodo}</td>
              <td class="amount"><Money value={row.ingresos_ml} /></td>
              <td class="amount"><Money value={row.gastos_ml} /></td>
              <td class="amount result"><Money value={row.resultado_ml} /></td>
            </tr>
          {/each}
        </tbody>
      </table>
    {:else}
      <div class="empty-state">Sin resultado mensual para mostrar.</div>
    {/if}
  </div>

  <EVSectionTitle
    title="PNL por nivel 1"
    subtitle="Vista agregada por primera jerarquia financiera para identificar rapidamente composicion del resultado."
  />

  <EVFinancialTable
    data={pnl_nivel1}
    levelColumns={['empresa', 'periodo', 'nivel1']}
    metaColumns={['movimientos']}
    amountColumn="monto_ml"
  />

  <EVSectionTitle
    title="PNL estructurado"
    subtitle="Estado de resultados con niveles financieros, subtotales y alertas discretas para partidas que requieren revision."
  />

  <EVFinancialTable
    data={pnl_estructurado}
    levelColumns={['nivel1', 'nivel2', 'nivel3']}
    metaColumns={['empresa', 'periodo', 'movimientos']}
    amountColumn="monto_ml"
  />

  <EVSectionTitle
    title="Cuentas por revisar"
    subtitle="Cuentas procesadas por fallback o sin regla exacta. El objetivo es depurarlas en etl/config/pnl_mapping_rules.json."
  />

  <EVFinancialTable
    data={cuentas_revision}
    levelColumns={['cuenta_codigo', 'cuenta_nombre', 'nivel1']}
    metaColumns={['empresa', 'regla_aplicada', 'tipo_regla', 'movimientos']}
    amountColumn="monto_ml"
  />
</EVTheme>

<style>
  .hero {
    border-bottom: 1px solid var(--ev-border, #e2d9d0);
    margin-bottom: 16px;
    padding-bottom: 42px;
  }

  .eyebrow {
    color: var(--ev-red, #e60000);
    font-size: 0.76rem;
    font-weight: 700;
    letter-spacing: 0.16em;
    margin-bottom: 18px;
    text-transform: uppercase;
  }

  h1 {
    color: var(--ev-text, #303030);
    font-family: var(--ev-font-head, Georgia, "Times New Roman", serif);
    font-size: clamp(2.8rem, 7vw, 5.6rem);
    font-weight: 400;
    letter-spacing: -0.055em;
    line-height: 0.98;
    margin: 0;
  }

  .hero p {
    color: var(--ev-text-muted, #666666);
    font-size: 1.05rem;
    line-height: 1.6;
    margin: 22px 0 0;
    max-width: 760px;
  }

  .kpi-grid {
    display: grid;
    gap: 18px;
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .load-note {
    background: var(--ev-surface, #f8f5f0);
    border: 1px solid var(--ev-border, #e2d9d0);
    display: grid;
    gap: 18px;
    grid-template-columns: 2fr 1fr 1fr;
    margin-top: 18px;
    padding: 20px 24px;
  }

  .note-label {
    color: var(--ev-text-muted, #666666);
    display: block;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    margin-bottom: 6px;
    text-transform: uppercase;
  }

  .load-note strong {
    color: var(--ev-text, #303030);
    font-weight: 700;
  }

  .monthly-table {
    border: 1px solid var(--ev-border, #e2d9d0);
    overflow-x: auto;
  }

  .monthly-table table {
    background: var(--ev-white, #ffffff);
    border-collapse: collapse;
    min-width: 720px;
    width: 100%;
  }

  .monthly-table th,
  .monthly-table td {
    border-bottom: 1px solid var(--ev-border, #e2d9d0);
    padding: 14px 16px;
    text-align: left;
  }

  .monthly-table tbody tr:last-child td {
    border-bottom: 0;
  }

  .monthly-table .amount {
    text-align: right;
    white-space: nowrap;
  }

  .monthly-table .result {
    font-weight: 700;
  }

  .empty-state {
    background: var(--ev-surface, #f8f5f0);
    color: var(--ev-text-muted, #666666);
    padding: 22px;
  }

  @media (max-width: 920px) {
    .kpi-grid,
    .load-note {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 620px) {
    .kpi-grid,
    .load-note {
      grid-template-columns: 1fr;
    }
  }
</style>
