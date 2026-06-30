<script>
  export let compact = false;
</script>

<div class:compact class="ev-theme">
  <slot />
</div>

<style>
  :global(:root) {
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

  :global(body) {
    background: var(--ev-bg);
    color: var(--ev-text);
    font-family: var(--ev-font-text);
  }

  :global(h1),
  :global(h2),
  :global(h3) {
    color: var(--ev-text);
    font-family: var(--ev-font-head);
    letter-spacing: -0.02em;
  }

  :global(a) {
    color: var(--ev-text);
    text-decoration-color: var(--ev-red);
    text-underline-offset: 3px;
  }

  :global(table) {
    border-collapse: collapse;
    color: var(--ev-text);
    font-family: var(--ev-font-text);
  }

  :global(th) {
    background: var(--ev-surface);
    color: var(--ev-gray-2);
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  :global(td),
  :global(th) {
    border-bottom: 1px solid var(--ev-border);
  }

  .ev-theme {
    background: var(--ev-bg);
    color: var(--ev-text);
    font-family: var(--ev-font-text);
    margin: 0 auto;
    max-width: 1180px;
    padding: var(--ev-space-xl) var(--ev-space-lg) var(--ev-space-xxl);
  }

  .compact {
    padding-top: var(--ev-space-lg);
  }

  @media (max-width: 760px) {
    .ev-theme {
      padding: var(--ev-space-lg) var(--ev-space-md) var(--ev-space-xl);
    }
  }
</style>
