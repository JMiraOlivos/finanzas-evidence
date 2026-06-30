<script>
  import Money from "./Money.svelte";

  export let data = [];
  export let labelColumn = "nivel1";
  export let amountColumn = "monto_ml";
  export let levelColumns = [];
  export let metaColumns = [];
  export let emptyMessage = "Sin datos para mostrar.";

  const labelFor = (column) =>
    String(column)
      .replace(/_/g, " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase());

  const getRows = (input) => {
    if (Array.isArray(input)) return input;
    if (Array.isArray(input?.rows)) return input.rows;
    if (Array.isArray(input?.data)) return input.data;
    return [];
  };

  $: rows = getRows(data);
  $: visibleLevelColumns = levelColumns.length ? levelColumns : [labelColumn];
</script>

<div class="table-wrap">
  {#if rows.length}
    <table class="financial-table">
      <thead>
        <tr>
          {#each visibleLevelColumns as column}
            <th>{labelFor(column)}</th>
          {/each}
          {#each metaColumns as column}
            <th>{labelFor(column)}</th>
          {/each}
          <th class="amount">Monto</th>
        </tr>
      </thead>
      <tbody>
        {#each rows as row}
          <tr class:subtotal={row.es_subtotal} class:review={row.requiere_revision || row.contiene_fallback}>
            {#each visibleLevelColumns as column, index}
              <td class={`level level-${index + 1}`}>
                {row[column] ?? "-"}
                {#if index === visibleLevelColumns.length - 1 && (row.requiere_revision || row.contiene_fallback)}
                  <span class="badge">Revisar</span>
                {/if}
              </td>
            {/each}
            {#each metaColumns as column}
              <td class="meta">{row[column] ?? "-"}</td>
            {/each}
            <td class="amount"><Money value={row[amountColumn]} /></td>
          </tr>
        {/each}
      </tbody>
    </table>
  {:else}
    <div class="empty">{emptyMessage}</div>
  {/if}
</div>

<style>
  .table-wrap {
    border: 1px solid var(--ev-border, #e2d9d0);
    overflow-x: auto;
  }

  .financial-table {
    background: var(--ev-white, #ffffff);
    border-collapse: collapse;
    color: var(--ev-text, #303030);
    font-family: var(--ev-font-text, Arial, Helvetica, sans-serif);
    min-width: 760px;
    width: 100%;
  }

  th {
    background: var(--ev-surface, #f8f5f0);
    border-bottom: 1px solid var(--ev-border, #e2d9d0);
    color: var(--ev-gray-2, #404040);
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    padding: 14px 16px;
    text-align: left;
    text-transform: uppercase;
    white-space: nowrap;
  }

  td {
    border-bottom: 1px solid var(--ev-border, #e2d9d0);
    padding: 14px 16px;
    vertical-align: top;
  }

  tbody tr:last-child td {
    border-bottom: 0;
  }

  .level-1 {
    font-weight: 700;
  }

  .level-2,
  .level-3,
  .meta {
    color: var(--ev-text-muted, #666666);
  }

  .amount {
    text-align: right;
    white-space: nowrap;
  }

  tr.subtotal td {
    background: var(--ev-surface, #f8f5f0);
    border-top: 2px solid var(--ev-text, #303030);
    font-weight: 700;
  }

  tr.review td {
    background: linear-gradient(90deg, rgba(248, 245, 240, 0.9), #ffffff 62%);
  }

  .badge {
    border: 1px solid var(--ev-dark-red, #910f05);
    color: var(--ev-dark-red, #910f05);
    display: inline-block;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    margin-left: 10px;
    padding: 2px 6px;
    text-transform: uppercase;
    vertical-align: middle;
  }

  .empty {
    background: var(--ev-surface, #f8f5f0);
    border: 1px solid var(--ev-border, #e2d9d0);
    color: var(--ev-text-muted, #666666);
    padding: 22px;
  }
</style>
