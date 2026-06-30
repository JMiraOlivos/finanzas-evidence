<script>
  export let value = 0;
  export let className = "";

  $: raw = Number(value ?? 0);
  $: isNegative = raw < 0;
  $: formattedNumber = new Intl.NumberFormat("es-CL", {
    maximumFractionDigits: 0,
    minimumFractionDigits: 0
  }).format(Math.abs(raw));
  $: formatted = `$ ${formattedNumber}`;
  $: display = isNegative ? `(${formatted})` : formatted;
</script>

<span class={`money ${isNegative ? "negative" : ""} ${className}`}>{display}</span>

<style>
  .money {
    display: inline-block;
    font-variant-numeric: tabular-nums;
    text-align: right;
    white-space: nowrap;
  }

  .negative {
    color: var(--ev-negative, #e60000);
    font-weight: 600;
  }
</style>
