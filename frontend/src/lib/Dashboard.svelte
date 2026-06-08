<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { Chart, registerables } from 'chart.js';
  import {
    // Postgres analytics (always available — demo + prod)
    fetchSentimentRolling,
    fetchSourcesRanked,
    fetchSentimentBreakdown,
    fetchEntityMomentum,
    fetchCategoriesDaily,
    // BigQuery analytics (additive, only when enabled)
    fetchTopEntities,
    fetchEntitySentiment,
    fetchEntitySentimentTimeline,
    fetchNlpCategories,
    type RollingSentimentPoint,
    type SourceRanked,
    type SentimentBreakdownRow,
    type EntityMomentum,
    type CategoryDailyPoint,
    type TopEntity,
    type EntitySentiment,
    type EntitySentimentTimelinePoint,
    type NlpCategoryBreakdown,
  } from './api';
  import { theme } from './theme';

  Chart.register(...registerables);

  let days = 30;
  const ROLLING_WINDOW = 7;
  let loading = true;
  let error = '';

  // ── Postgres-backed data (the always-on core) ──────────────────────────
  let rolling: RollingSentimentPoint[] = [];
  let ranked: SourceRanked[] = [];
  let breakdown: SentimentBreakdownRow[] = [];
  let momentum: EntityMomentum[] = [];
  let catDaily: CategoryDailyPoint[] = [];

  // ── BigQuery-backed data (additive bonus row when ENABLE_BIGQUERY) ──────
  let bqEntities: TopEntity[] = [];
  let bqEntitySentiment: EntitySentiment[] = [];
  let bqEntityTimeline: EntitySentimentTimelinePoint[] = [];
  let bqCategories: NlpCategoryBreakdown[] = [];
  // Entity-type filter for the BQ entity charts ('' = all types).
  let entityType = '';
  $: hasBigQuery =
    bqEntities.length > 0 ||
    bqEntitySentiment.length > 0 ||
    bqEntityTimeline.length > 0 ||
    bqCategories.length > 0;

  // Sentiment palette — emerald / slate / rose, deliberately distinct from
  // the indigo brand accent so a sentiment colour can never read as "brand".
  const C = {
    pos: '#34D399',
    neu: '#94A3B8',
    neg: '#FB7185',
    accent: '#7C5CFC',
    accentDim: 'rgba(124,92,252,0.15)',
  };

  function sentimentColor(score: number | null | undefined): string {
    const s = score ?? 0;
    if (s > 0.1) return C.pos;
    if (s < -0.1) return C.neg;
    return C.neu;
  }

  // ── KPI derivation from the GROUPING SETS grand-total / label subtotals ──
  type Kpis = {
    total: number;
    positivePct: number;
    neutralPct: number;
    negativePct: number;
    sources: number;
  };
  let kpis: Kpis = { total: 0, positivePct: 0, neutralPct: 0, negativePct: 0, sources: 0 };

  function deriveKpis(): void {
    // Grand-total row: both grouping flags = 1 (category and label rolled up).
    const grand = breakdown.find(
      (r) => r.is_category_total === 1 && r.is_label_total === 1,
    );
    const total = grand?.article_count ?? 0;

    // Per-label subtotals: label present (flag 0), category rolled up (flag 1).
    const labelTotal = (label: string): number =>
      breakdown.find(
        (r) =>
          r.is_category_total === 1 &&
          r.is_label_total === 0 &&
          r.sentiment_label === label,
      )?.article_count ?? 0;

    const pct = (n: number): number => (total > 0 ? Math.round((n / total) * 100) : 0);

    kpis = {
      total,
      positivePct: pct(labelTotal('positive')),
      neutralPct: pct(labelTotal('neutral')),
      negativePct: pct(labelTotal('negative')),
      sources: ranked.length,
    };
  }

  // ── Chart instances + canvas refs ──────────────────────────────────────
  let rollingChart: Chart | null = null;
  let rankedChart: Chart | null = null;
  let breakdownChart: Chart | null = null;
  let momentumChart: Chart | null = null;
  let catChart: Chart | null = null;
  let bqEntityChart: Chart | null = null;
  let bqSentimentChart: Chart | null = null;
  let bqTimelineChart: Chart | null = null;
  let bqCatChart: Chart | null = null;

  let rollingCanvas: HTMLCanvasElement;
  let rankedCanvas: HTMLCanvasElement;
  let breakdownCanvas: HTMLCanvasElement;
  let momentumCanvas: HTMLCanvasElement;
  let catCanvas: HTMLCanvasElement;
  let bqEntityCanvas: HTMLCanvasElement;
  let bqSentimentCanvas: HTMLCanvasElement;
  let bqTimelineCanvas: HTMLCanvasElement;
  let bqCatCanvas: HTMLCanvasElement;

  // Resolve theme-aware chart colours from the live CSS custom properties so
  // the charts follow the dark/light token system instead of hardcoding.
  function themeVars(): { grid: string; tick: string; panel: string; border: string; text: string } {
    const css = getComputedStyle(document.documentElement);
    const v = (name: string, fallback: string) => css.getPropertyValue(name).trim() || fallback;
    return {
      grid: 'rgba(148,163,184,0.15)',
      tick: v('--text-sec', '#94A3B8'),
      panel: v('--bg-panel', '#111827'),
      border: v('--border', '#273244'),
      text: v('--text-pri', '#F8FAFC'),
    };
  }

  function baseOptions(indexAxis: 'x' | 'y' = 'x'): Record<string, unknown> {
    const tv = themeVars();
    return {
      indexAxis,
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          padding: 10,
          cornerRadius: 6,
          backgroundColor: tv.panel,
          borderColor: tv.border,
          borderWidth: 1,
          titleColor: tv.text,
          bodyColor: tv.tick,
        },
      },
      scales: {
        x: { grid: { color: tv.grid }, ticks: { color: tv.tick } },
        y: { grid: { color: tv.grid }, ticks: { color: tv.tick } },
      },
    };
  }

  async function loadData() {
    loading = true;
    error = '';
    try {
      // Core Postgres analytics — these must succeed for the dashboard to
      // be useful, so a failure here surfaces as the page error.
      // entities/momentum and categories/daily cap the window server-side
      // (60 and 90 days). Clamp to those maxima so the wider ranges still
      // pull the most data the endpoint allows rather than 400-ing.
      [rolling, ranked, breakdown, momentum, catDaily] = await Promise.all([
        fetchSentimentRolling(days, ROLLING_WINDOW),
        fetchSourcesRanked(days),
        fetchSentimentBreakdown(days),
        fetchEntityMomentum(Math.min(days, 60)),
        fetchCategoriesDaily(Math.min(days, 90)),
      ]);
      deriveKpis();

      // BigQuery analytics are best-effort: if BigQuery is disabled the
      // endpoints return [] and the bonus row simply doesn't render. The
      // entity-type filter (entityType) narrows the three entity charts;
      // '' means "all types" and is sent as undefined.
      [bqEntities, bqEntitySentiment, bqEntityTimeline, bqCategories] = await Promise.all([
        fetchTopEntities(days, entityType || undefined, 12).catch(() => []),
        fetchEntitySentiment(days, entityType || undefined, 12).catch(() => []),
        fetchEntitySentimentTimeline(days, entityType || undefined, 8).catch(() => []),
        fetchNlpCategories(days, 12).catch(() => []),
      ]);

      setTimeout(renderCharts, 0);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load analytics';
    } finally {
      loading = false;
    }
  }

  function destroyCharts() {
    for (const c of [
      rollingChart, rankedChart, breakdownChart, momentumChart, catChart,
      bqEntityChart, bqSentimentChart, bqTimelineChart, bqCatChart,
    ]) {
      c?.destroy();
    }
    rollingChart = rankedChart = breakdownChart = null;
    momentumChart = catChart = null;
    bqEntityChart = bqSentimentChart = bqTimelineChart = bqCatChart = null;
  }

  function renderCharts() {
    destroyCharts();
    renderRolling();
    renderRanked();
    renderBreakdown();
    renderMomentum();
    renderCatCumulative();
    if (hasBigQuery) {
      renderBqEntities();
      renderBqEntitySentiment();
      renderBqTimeline();
      renderBqCategories();
    }
  }

  // 1 — Rolling-average sentiment trend (window function), with the raw
  //     daily average overlaid faintly so the smoothing is visible.
  function renderRolling() {
    if (!rollingCanvas || !rolling.length) return;
    const labels = rolling.map((r) => r.day);
    const opts = baseOptions('x') as Record<string, any>;
    opts.plugins.tooltip.callbacks = {
      label: (ctx: any) => ` ${ctx.dataset.label}: ${Number(ctx.raw).toFixed(3)}`,
    };
    opts.scales.y.suggestedMin = -1;
    opts.scales.y.suggestedMax = 1;
    rollingChart = new Chart(rollingCanvas, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Daily avg',
            data: rolling.map((r) => r.avg_sentiment),
            borderColor: C.neu,
            backgroundColor: 'rgba(148,163,184,0.08)',
            borderWidth: 1,
            borderDash: [4, 3],
            pointRadius: 0,
            tension: 0.2,
            fill: false,
          },
          {
            label: `${ROLLING_WINDOW}-day rolling avg`,
            data: rolling.map((r) => r.rolling_avg),
            borderColor: C.accent,
            backgroundColor: C.accentDim,
            borderWidth: 2.5,
            pointRadius: 0,
            pointHoverRadius: 4,
            tension: 0.35,
            fill: true,
          },
        ],
      },
      options: opts,
    });
  }

  // 2 — Source positivity ranking (CTE + RANK window fn). Bars coloured by
  //     avg sentiment; tooltip exposes the rank and volatility (stddev).
  function renderRanked() {
    if (!rankedCanvas || !ranked.length) return;
    const opts = baseOptions('y') as Record<string, any>;
    opts.scales.y.grid = { display: false };
    opts.plugins.tooltip.callbacks = {
      label: (ctx: any) => {
        const r = ranked[ctx.dataIndex];
        const vol = r.sentiment_stddev != null ? r.sentiment_stddev.toFixed(2) : '—';
        return [
          ` avg sentiment: ${Number(r.avg_sentiment).toFixed(3)}`,
          ` rank #${r.positivity_rank} · ${r.article_count} articles · σ ${vol}`,
        ];
      },
    };
    rankedChart = new Chart(rankedCanvas, {
      type: 'bar',
      data: {
        labels: ranked.map((r) => r.source_name),
        datasets: [
          {
            label: 'Avg sentiment',
            data: ranked.map((r) => r.avg_sentiment),
            backgroundColor: ranked.map((r) => sentimentColor(r.avg_sentiment)),
            borderRadius: 4,
            borderSkipped: false,
          },
        ],
      },
      options: opts,
    });
  }

  // 3 — Category × sentiment matrix (GROUPING SETS). Only the detail rows
  //     (both grouping flags 0); subtotals/grand-total feed the KPIs instead.
  function renderBreakdown() {
    if (!breakdownCanvas) return;
    const detail = breakdown.filter(
      (r) => r.is_category_total === 0 && r.is_label_total === 0,
    );
    if (!detail.length) return;

    const categories = [...new Set(detail.map((r) => r.category))];
    const labels = ['positive', 'neutral', 'negative'] as const;
    const labelColor = { positive: C.pos, neutral: C.neu, negative: C.neg };

    const opts = baseOptions('x') as Record<string, any>;
    opts.scales.x.stacked = true;
    opts.scales.y.stacked = true;
    opts.scales.y.beginAtZero = true;
    opts.plugins.legend = { display: true, position: 'bottom', labels: { color: themeVars().tick, boxWidth: 10 } };

    breakdownChart = new Chart(breakdownCanvas, {
      type: 'bar',
      data: {
        labels: categories,
        datasets: labels.map((label) => ({
          label: label.charAt(0).toUpperCase() + label.slice(1),
          data: categories.map(
            (cat) =>
              detail.find((r) => r.category === cat && r.sentiment_label === label)
                ?.article_count ?? 0,
          ),
          backgroundColor: labelColor[label],
          borderRadius: 3,
        })),
      },
      options: opts,
    });
  }

  // 4 — Trending entities (two-CTE momentum). Diverging bars: green = rising,
  //     rose = falling, by period-over-period growth.
  function renderMomentum() {
    if (!momentumCanvas || !momentum.length) return;
    // Top movers in both directions: highest-growth and lowest-growth ends.
    const sorted = [...momentum].sort((a, b) => b.growth_pct - a.growth_pct);
    const top = sorted.slice(0, 6);
    const bottom = sorted.slice(-4).filter((b) => !top.includes(b));
    const picks = [...top, ...bottom];

    const opts = baseOptions('y') as Record<string, any>;
    opts.scales.y.grid = { display: false };
    opts.scales.x.ticks = { color: themeVars().tick, callback: (v: number) => `${v}%` };
    opts.plugins.tooltip.callbacks = {
      label: (ctx: any) => {
        const e = picks[ctx.dataIndex];
        return [
          ` ${e.growth_pct > 0 ? '▲' : '▼'} ${e.growth_pct}% period-over-period`,
          ` ${e.previous_mentions} → ${e.recent_mentions} mentions`,
        ];
      },
    };
    momentumChart = new Chart(momentumCanvas, {
      type: 'bar',
      data: {
        labels: picks.map((e) => `${e.entity_name} (${e.entity_type})`),
        datasets: [
          {
            label: 'Growth %',
            data: picks.map((e) => e.growth_pct),
            backgroundColor: picks.map((e) => (e.growth_pct >= 0 ? C.pos : C.neg)),
            borderRadius: 3,
            borderSkipped: false,
          },
        ],
      },
      options: opts,
    });
  }

  // 5 — Cumulative article volume per category over time (SUM() OVER window).
  function renderCatCumulative() {
    if (!catCanvas || !catDaily.length) return;
    const days_ = [...new Set(catDaily.map((r) => r.day))].sort();
    const categories = [...new Set(catDaily.map((r) => r.category))];
    // Stable per-category colour ramp around the accent hue.
    const ramp = ['#7C5CFC', '#34D399', '#FB7185', '#F59E0B', '#38BDF8', '#A78BFA', '#94A3B8'];

    const opts = baseOptions('x') as Record<string, any>;
    opts.scales.y.beginAtZero = true;
    opts.plugins.legend = { display: true, position: 'bottom', labels: { color: themeVars().tick, boxWidth: 10 } };

    catChart = new Chart(catCanvas, {
      type: 'line',
      data: {
        labels: days_,
        datasets: categories.map((cat, i) => ({
          label: cat,
          // Latest known cumulative value per day (carries forward visually).
          data: days_.map(
            (d) =>
              catDaily.find((r) => r.day === d && r.category === cat)
                ?.cumulative_articles ?? null,
          ),
          borderColor: ramp[i % ramp.length],
          backgroundColor: ramp[i % ramp.length] + '20',
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.3,
          spanGaps: true,
          fill: false,
        })),
      },
      options: opts,
    });
  }

  // 6a/6b — BigQuery bonus charts (only rendered when hasBigQuery).
  function renderBqEntities() {
    if (!bqEntityCanvas || !bqEntities.length) return;
    const opts = baseOptions('y') as Record<string, any>;
    opts.scales.y.grid = { display: false };
    opts.plugins.tooltip.callbacks = { label: (ctx: any) => ` ${ctx.raw} mentions` };
    bqEntityChart = new Chart(bqEntityCanvas, {
      type: 'bar',
      data: {
        labels: bqEntities.map((e) => `${e.entity_name} (${e.entity_type})`),
        datasets: [
          {
            label: 'Articles',
            data: bqEntities.map((e) => e.article_count),
            backgroundColor: bqEntities.map((e) => sentimentColor(e.avg_sentiment_score)),
            borderRadius: 3,
            borderSkipped: false,
          },
        ],
      },
      options: opts,
    });
  }

  // 6c — Most positively / negatively covered names (BQ get_entity_sentiment).
  //      Diverging horizontal bars: green = positive coverage, rose = negative.
  function renderBqEntitySentiment() {
    if (!bqSentimentCanvas || !bqEntitySentiment.length) return;
    const sorted = [...bqEntitySentiment].sort(
      (a, b) => (b.avg_sentiment_score ?? 0) - (a.avg_sentiment_score ?? 0),
    );
    const opts = baseOptions('y') as Record<string, any>;
    opts.scales.y.grid = { display: false };
    opts.scales.x.suggestedMin = -1;
    opts.scales.x.suggestedMax = 1;
    opts.plugins.tooltip.callbacks = {
      label: (ctx: any) => {
        const e = sorted[ctx.dataIndex];
        return [
          ` avg sentiment: ${(e.avg_sentiment_score ?? 0).toFixed(3)}`,
          ` ${e.article_count} articles`,
        ];
      },
    };
    bqSentimentChart = new Chart(bqSentimentCanvas, {
      type: 'bar',
      data: {
        labels: sorted.map((e) => `${e.entity_name} (${e.entity_type})`),
        datasets: [
          {
            label: 'Avg sentiment',
            data: sorted.map((e) => e.avg_sentiment_score ?? 0),
            backgroundColor: sorted.map((e) => sentimentColor(e.avg_sentiment_score)),
            borderRadius: 3,
            borderSkipped: false,
          },
        ],
      },
      options: opts,
    });
  }

  // 6d — Entity sentiment over time (BQ get_entity_sentiment_timeline).
  //      One line per top-N entity; y = daily avg sentiment in [-1, 1].
  function renderBqTimeline() {
    if (!bqTimelineCanvas || !bqEntityTimeline.length) return;
    const days_ = [...new Set(bqEntityTimeline.map((r) => r.date))].sort();
    const entities = [...new Set(bqEntityTimeline.map((r) => r.entity_name))];
    // Stable per-entity colour ramp around the accent hue (matches renderCatCumulative).
    const ramp = ['#7C5CFC', '#34D399', '#FB7185', '#F59E0B', '#38BDF8', '#A78BFA', '#94A3B8', '#F472B6'];

    const opts = baseOptions('x') as Record<string, any>;
    opts.scales.y.suggestedMin = -1;
    opts.scales.y.suggestedMax = 1;
    opts.plugins.legend = { display: true, position: 'bottom', labels: { color: themeVars().tick, boxWidth: 10 } };
    opts.plugins.tooltip.callbacks = {
      label: (ctx: any) =>
        ` ${ctx.dataset.label}: ${ctx.raw == null ? '—' : Number(ctx.raw).toFixed(3)}`,
    };

    bqTimelineChart = new Chart(bqTimelineCanvas, {
      type: 'line',
      data: {
        labels: days_,
        datasets: entities.map((name, i) => ({
          label: name,
          data: days_.map(
            (d) =>
              bqEntityTimeline.find((r) => r.date === d && r.entity_name === name)
                ?.avg_sentiment_score ?? null,
          ),
          borderColor: ramp[i % ramp.length],
          backgroundColor: ramp[i % ramp.length] + '20',
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.3,
          spanGaps: true,
          fill: false,
        })),
      },
      options: opts,
    });
  }

  function renderBqCategories() {
    if (!bqCatCanvas || !bqCategories.length) return;
    const opts = baseOptions('y') as Record<string, any>;
    opts.scales.y.grid = { display: false };
    opts.plugins.tooltip.callbacks = { label: (ctx: any) => ` ${ctx.raw} articles` };
    bqCatChart = new Chart(bqCatCanvas, {
      type: 'bar',
      data: {
        labels: bqCategories.map((c) => c.category_name),
        datasets: [
          {
            label: 'Articles',
            data: bqCategories.map((c) => c.article_count),
            backgroundColor: bqCategories.map((c) => sentimentColor(c.avg_sentiment_score)),
            borderRadius: 3,
            borderSkipped: false,
          },
        ],
      },
      options: opts,
    });
  }

  function handleDaysChange(event: Event) {
    days = parseInt((event.target as HTMLSelectElement).value);
    loadData();
  }

  function handleEntityTypeChange(event: Event) {
    entityType = (event.target as HTMLSelectElement).value;
    loadData();
  }

  let mounted = false;

  onMount(() => {
    Chart.defaults.font.family = "'Space Grotesk', system-ui, sans-serif";
    Chart.defaults.font.size = 11;
    mounted = true;
    loadData();
  });
  onDestroy(() => destroyCharts());

  // Re-render the charts when the theme flips so grid/tick/tooltip colours
  // follow the token system. Guarded by `mounted` + data presence so it never
  // fires before the first load.
  $: if (mounted && $theme && !loading && rolling.length >= 0) {
    void $theme;
    renderCharts();
  }
</script>

<div class="dashboard">
  <div class="controls">
    <div>
      <h2 class="page-title">Analytics Dashboard</h2>
      <p class="page-subtitle">
        Sentiment scored by Google's Natural Language AI on every ingested
        article, then aggregated live from the database.
      </p>
    </div>
    <select on:change={handleDaysChange} value={days} aria-label="Time range">
      <option value={7}>Last 7 days</option>
      <option value={30}>Last 30 days</option>
      <option value={90}>Last 90 days</option>
      <option value={365}>Last year</option>
    </select>
  </div>

  {#if error}
    <div class="error-banner" role="alert">
      <span class="error-icon" aria-hidden="true">⚠</span>
      <span style="flex:1">{error}</span>
    </div>
  {/if}

  {#if loading}
    <div style="text-align:center;padding:var(--sp-10) 0">
      <div class="spinner"></div>
      <p class="text-sec">Loading analytics…</p>
    </div>
  {:else}
    <!-- KPI tiles (derived from the GROUPING SETS grand-total + subtotals) -->
    <div class="kpi-row">
      <div class="kpi-tile" style="--accent:#7C5CFC">
        <span class="kpi-label">Total Articles</span>
        <span class="kpi-value">{kpis.total.toLocaleString()}</span>
      </div>
      <div class="kpi-tile" style="--accent:#34D399">
        <span class="kpi-label">Positive</span>
        <span class="kpi-value">{kpis.positivePct}%</span>
      </div>
      <div class="kpi-tile" style="--accent:#94A3B8">
        <span class="kpi-label">Neutral</span>
        <span class="kpi-value">{kpis.neutralPct}%</span>
      </div>
      <div class="kpi-tile" style="--accent:#FB7185">
        <span class="kpi-label">Negative</span>
        <span class="kpi-value">{kpis.negativePct}%</span>
      </div>
      <div class="kpi-tile" style="--accent:#7C5CFC">
        <span class="kpi-label">Sources Tracked</span>
        <span class="kpi-value">{kpis.sources}</span>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <h3 class="chart-title">Mood Over Time</h3>
        <p class="chart-sub">
          How positive or negative the news has felt each day. The bold line is a
          7-day rolling average that smooths out daily noise to reveal the trend.
        </p>
        {#if rolling.length}
          <div class="chart-wrap"><canvas bind:this={rollingCanvas}></canvas></div>
        {:else}
          <p class="empty">No sentiment data in this range</p>
        {/if}
      </div>

      <div class="card">
        <h3 class="chart-title">Which Sources Are Most Positive</h3>
        <p class="chart-sub">
          News outlets ranked by the average sentiment of their coverage. Hover a
          bar for its rank, article count, and how much its tone varies.
        </p>
        {#if ranked.length}
          <div class="chart-wrap"><canvas bind:this={rankedCanvas}></canvas></div>
        {:else}
          <p class="empty">No source data in this range</p>
        {/if}
      </div>

      <div class="card">
        <h3 class="chart-title">Sentiment by Topic</h3>
        <p class="chart-sub">
          The mix of positive, neutral, and negative articles within each news
          category.
        </p>
        {#if breakdown.length}
          <div class="chart-wrap"><canvas bind:this={breakdownCanvas}></canvas></div>
        {:else}
          <p class="empty">No category data in this range</p>
        {/if}
      </div>

      <div class="card">
        <h3 class="chart-title">Trending Names</h3>
        <p class="chart-sub">
          People and organizations gaining or losing coverage compared with the
          previous period. Green is rising, rose is falling.
        </p>
        {#if momentum.length}
          <div class="chart-wrap"><canvas bind:this={momentumCanvas}></canvas></div>
        {:else}
          <p class="empty">No entity momentum in this range</p>
        {/if}
      </div>

      <div class="card card-wide">
        <h3 class="chart-title">Coverage Growth by Topic</h3>
        <p class="chart-sub">
          Total articles accumulated per category over time — steeper lines mean
          a topic is being covered more heavily.
        </p>
        {#if catDaily.length}
          <div class="chart-wrap"><canvas bind:this={catCanvas}></canvas></div>
        {:else}
          <p class="empty">No category timeline in this range</p>
        {/if}
      </div>
    </div>

    {#if hasBigQuery}
      <div class="bq-header">
        <div>
          <h3 class="chart-title">AI-Enriched Insights</h3>
          <p class="chart-sub">
            Entities and topics detected by Google's Natural Language AI,
            aggregated over the full history in the data warehouse.
          </p>
        </div>
        <div class="bq-header-controls">
          <select on:change={handleEntityTypeChange} value={entityType} aria-label="Entity type filter">
            <option value="">All types</option>
            <option value="PERSON">People</option>
            <option value="ORGANIZATION">Organizations</option>
            <option value="LOCATION">Locations</option>
            <option value="EVENT">Events</option>
            <option value="WORK_OF_ART">Works of art</option>
            <option value="CONSUMER_GOOD">Consumer goods</option>
          </select>
          <span class="bq-badge" title="Served from BigQuery — Google's analytics data warehouse">Data warehouse</span>
        </div>
      </div>
      <div class="grid-2">
        <div class="card">
          <h3 class="chart-title">Most-Mentioned People &amp; Organizations</h3>
          <p class="chart-sub">
            Names automatically extracted from each article by Google's Natural
            Language AI. Bar colour shows the average sentiment of the coverage
            mentioning them.
          </p>
          {#if bqEntities.length}
            <div class="chart-wrap"><canvas bind:this={bqEntityCanvas}></canvas></div>
          {:else}
            <p class="empty">No entity data</p>
          {/if}
        </div>
        <div class="card">
          <h3 class="chart-title">Most Positively &amp; Negatively Covered Names</h3>
          <p class="chart-sub">
            Entities ranked by the average sentiment of the articles mentioning
            them. Green is favourable coverage, rose is unfavourable.
          </p>
          {#if bqEntitySentiment.length}
            <div class="chart-wrap"><canvas bind:this={bqSentimentCanvas}></canvas></div>
          {:else}
            <p class="empty">No entity sentiment data</p>
          {/if}
        </div>
        <div class="card card-wide">
          <h3 class="chart-title">How Coverage Sentiment Shifts Over Time</h3>
          <p class="chart-sub">
            Daily average sentiment for the most-mentioned names, tracked across
            the selected window. Each line is one entity.
          </p>
          {#if bqEntityTimeline.length}
            <div class="chart-wrap"><canvas bind:this={bqTimelineCanvas}></canvas></div>
          {:else}
            <p class="empty">No entity timeline data</p>
          {/if}
        </div>
        <div class="card card-wide">
          <h3 class="chart-title">What the News Is About</h3>
          <p class="chart-sub">
            Each article is classified into topics by Google's Natural Language
            AI, which returns a confidence score per topic — only high-confidence
            labels are counted. Bar colour shows average sentiment.
          </p>
          {#if bqCategories.length}
            <div class="chart-wrap"><canvas bind:this={bqCatCanvas}></canvas></div>
          {:else}
            <p class="empty">No category data</p>
          {/if}
        </div>
      </div>
    {/if}
  {/if}
</div>

<style>
  .dashboard { padding: 0; }
  .error-icon { font-size: 16px; flex-shrink: 0; }

  .controls {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: var(--sp-6);
    gap: var(--sp-4);
    flex-wrap: wrap;
  }

  /* KPI row */
  .kpi-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: var(--sp-3);
    margin-bottom: var(--sp-6);
  }
  .kpi-tile {
    position: relative;
    overflow: hidden;
    background: var(--bg-panel);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: var(--sp-4) var(--sp-5);
    box-shadow: var(--shadow);
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  .kpi-tile::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: var(--accent, var(--border));
  }
  .kpi-label {
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-ter);
  }
  .kpi-value {
    font-size: 1.625rem;
    font-weight: 600;
    line-height: 1;
    color: var(--text-pri);
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.02em;
  }

  .grid-2 {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--sp-5);
  }
  @media (min-width: 900px) {
    .grid-2 { grid-template-columns: 1fr 1fr; }
    .card-wide { grid-column: 1 / -1; }
  }

  .card {
    background: var(--bg-panel);
    border: 1px solid var(--border);
    border-radius: var(--r-xl);
    padding: var(--sp-5);
    box-shadow: var(--shadow);
  }

  .chart-title {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--text-pri);
    letter-spacing: -0.01em;
  }
  .chart-sub {
    font-size: 0.75rem;
    color: var(--text-ter);
    margin: 0.25rem 0 0.9rem;
    line-height: 1.6;
    /* a hair of padding so descenders (y, g, p) clear the next element */
    padding-bottom: 1px;
  }

  .chart-wrap { position: relative; height: 260px; }
  .card-wide .chart-wrap { height: 300px; }

  .empty {
    text-align: center;
    padding: 2.5rem 0;
    font-size: 0.875rem;
    color: var(--text-ter);
  }

  .bq-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--sp-4);
    flex-wrap: wrap;
    margin: var(--sp-8) 0 var(--sp-4);
  }
  .bq-badge {
    font-size: 0.625rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--accent);
    background: var(--accent-dim);
    border: 1px solid rgba(124, 92, 252, 0.25);
    padding: 0.15rem 0.5rem;
    border-radius: 999px;
  }
  .bq-header-controls {
    display: flex;
    align-items: center;
    gap: var(--sp-3);
    flex-wrap: wrap;
  }

  /* Small phones: the auto-fit minmax(150px) packs 2 cramped KPI tiles and
     leaves the 5th stranded. Pin a clean 2-up grid with tighter padding, and
     give the time-range select the full row so it isn't a sub-44px target. */
  @media (max-width: 480px) {
    .kpi-row {
      grid-template-columns: 1fr 1fr;
      gap: var(--sp-2);
    }
    .kpi-tile { padding: var(--sp-3) var(--sp-4); }
    .kpi-value { font-size: 1.375rem; }
    .controls { flex-direction: column; align-items: stretch; }
    .controls select { width: 100%; }
  }
</style>
