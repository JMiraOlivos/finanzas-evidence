<script>
  import Money from "./Money.svelte";

  export let title = "";
  export let value = 0;
  export let subtitle = "";
  export let variant = "default";
  export let format = "money";

  $: numericValue = Number(value ?? 0);
  $: isNegative = format === "money" && numericValue < 0;
</script>

<article class={`kpi ${variant} ${isNegative ? "is-negative" : ""}`}>
  <div class="kpi-title">{title}</div>
  <div class="kpi-value">
    {#if format === "money"}
      <Money value={numericValue} />
    {:else}
      {numericValue.toLocaleString("es-CL")}
    {/if}
  </div>
  {#if subtitle}
    <div class="kpi-subtitle">{subtitle}</div>
  {/if}
</article>

<style>
  .kpi {
    background: var(--ev-white, #ffffff);
    border: 1px solid var(--ev-border, #e2d9d0);
    color: var(--ev-text, #303030);
    min-height: 136px;
    padding: 22px 24px;
  }

  .kpi.result {
    background: linear-gradient(180deg, var(--ev-white, #ffffff) 0%, var(--ev-surface, #f8f5f0) 100%);
    border-top: 3px solid var(--ev-text, #303030);
  }

  .kpi.warning {
    border-left: 3px solid var(--ev-red, #e60000);
  }

  .kpi-title {
    color: var(--ev-text-muted, #666666);
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    margin-bottom: 18px;
    text-transform: uppercase;
  }

  .kpi-value {
    color: var(--ev-text, #303030);
    font-family: var(--ev-font-head, Georgia, "Times New Roman", serif);
    font-size: clamp(1.65rem, 3vw, 2.35rem);
    letter-spacing: -0.04em;
    line-height: 1;
  }

  .is-negative .kpi-value,
  .warning .kpi-value {
    color: var(--ev-negative, #e60000);
  }

  .kpi-subtitle {
    color: var(--ev-text-muted, #666666);
    font-size: 0.86rem;
    line-height: 1.4;
    margin-top: 14px;
  }
</style>
