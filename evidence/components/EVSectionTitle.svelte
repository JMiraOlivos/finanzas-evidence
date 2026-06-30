<script>
  export let title = "";
  export let subtitle = "";
</script>

<section class="section-title">
  <div class="accent"></div>
  <h2>{title}</h2>
  {#if subtitle}
    <p>{subtitle}</p>
  {/if}
</section>

<style>
  .section-title {
    margin: 58px 0 22px;
  }

  .accent {
    background: var(--ev-red, #e60000);
    height: 2px;
    margin-bottom: 16px;
    width: 44px;
  }

  h2 {
    color: var(--ev-text, #303030);
    font-family: var(--ev-font-head, Georgia, "Times New Roman", serif);
    font-size: clamp(1.55rem, 2.4vw, 2.3rem);
    font-weight: 400;
    letter-spacing: -0.03em;
    line-height: 1.12;
    margin: 0;
  }

  p {
    color: var(--ev-text-muted, #666666);
    font-family: var(--ev-font-text, Arial, Helvetica, sans-serif);
    font-size: 0.98rem;
    line-height: 1.55;
    margin: 10px 0 0;
    max-width: 720px;
  }
</style>
