<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { Chart, registerables } from 'chart.js';
  import {
    fetchSentimentTrends,
    fetchSourceComparison,
    fetchTopEntities,
    fetchNlpCategories,
    fetchPipelineHealth,
    type SentimentTrendPoint,
    type SourceComparison,
    type TopEntity,
    type NlpCategoryBreakdown,
    type PipelineRun,
  } from './api';

  Chart.register(...registerables);

  let days = 30;
  let loading = true;
  let error = '';

  // Data
  let trends: SentimentTrendPoint[] = [];
  let sources: SourceComparison[] = [];
  let entities: TopEntity[] = [];
  let nlpCategories: NlpCategoryBreakdown[] = [];
  let pipeline: PipelineRun[] = [];

  // Chart instances (for cleanup)
  let trendChart: Chart | null = null;
  let sourceChart: Chart | null = null;
  let entityChart: Chart | null = null;
  let categoryChart: Chart | null = null;

  // Canvas refs
  let trendCanvas: HTMLCanvasElement;
  let sourceCanvas: HTMLCanvasElement;
  let entityCanvas: HTMLCanvasElement;
  let categoryCanvas: HTMLCanvasElement;

  const COLORS = {
    positive: '#16a34a',
    negative: '#dc2626',
    neutral: '#2563eb',
  };

  async function loadData() {
    loading = true;
    error = '';
    try {
      [trends, sources, entities, nlpCategories, pipeline] = await Promise.all([
        fetchSentimentTrends(days),
        fetchSourceComparison(days),
        fetchTopEntities(days, undefined, 15),
        fetchNlpCategories(days, 15),
        fetchPipelineHealth(Math.min(days, 90)),
      ]);
      // Defer chart rendering to next tick so canvases are mounted
      setTimeout(renderCharts, 0);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load analytics';
    } finally {
      loading = false;
    }
  }

  function destroyCharts() {
    trendChart?.destroy(); trendChart = null;
    sourceChart?.destroy(); sourceChart = null;
    entityChart?.destroy(); entityChart = null;
    categoryChart?.destroy(); categoryChart = null;
  }

  function renderCharts() {
    destroyCharts();
    renderTrendChart();
    renderSourceChart();
    renderEntityChart();
    renderCategoryChart();
  }

  function renderTrendChart() {
    if (!trendCanvas || !trends.length) return;

    // Group by date, then by label
    const dateMap = new Map<string, Record<string, number>>();
    for (const t of trends) {
      if (!dateMap.has(t.date)) dateMap.set(t.date, {});
      dateMap.get(t.date)![t.sentiment_label] = t.article_count;
    }
    const dates = [...dateMap.keys()].sort();

    trendChart = new Chart(trendCanvas, {
      type: 'line',
      data: {
        labels: dates,
        datasets: ['positive', 'negative', 'neutral'].map(label => ({
          label: label.charAt(0).toUpperCase() + label.slice(1),
          data: dates.map(d => dateMap.get(d)?.[label] ?? 0),
          borderColor: COLORS[label as keyof typeof COLORS],
          backgroundColor: COLORS[label as keyof typeof COLORS] + '20',
          tension: 0.3,
          fill: false,
        })),
      },
      options: {
        responsive: true,
        plugins: { legend: { position: 'top' } },
        scales: { y: { beginAtZero: true, title: { display: true, text: 'Articles' } } },
      },
    });
  }

  function renderSourceChart() {
    if (!sourceCanvas || !sources.length) return;

    // Get unique sources and build stacked data
    const sourceNames = [...new Set(sources.map(s => s.source_name))];
    const labels = ['positive', 'negative', 'neutral'];

    sourceChart = new Chart(sourceCanvas, {
      type: 'bar',
      data: {
        labels: sourceNames,
        datasets: labels.map(label => ({
          label: label.charAt(0).toUpperCase() + label.slice(1),
          data: sourceNames.map(src => {
            const match = sources.find(s => s.source_name === src && s.sentiment_label === label);
            return match?.percentage ?? 0;
          }),
          backgroundColor: COLORS[label as keyof typeof COLORS] + 'CC',
        })),
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        plugins: { legend: { position: 'top' } },
        scales: { x: { stacked: true, max: 100, title: { display: true, text: '%' } }, y: { stacked: true } },
      },
    });
  }

  function renderEntityChart() {
    if (!entityCanvas || !entities.length) return;

    entityChart = new Chart(entityCanvas, {
      type: 'bar',
      data: {
        labels: entities.map(e => `${e.entity_name} (${e.entity_type})`),
        datasets: [{
          label: 'Articles',
          data: entities.map(e => e.article_count),
          backgroundColor: entities.map(e => {
            const score = e.avg_sentiment_score ?? 0;
            if (score > 0.1) return COLORS.positive + 'CC';
            if (score < -0.1) return COLORS.negative + 'CC';
            return COLORS.neutral + 'CC';
          }),
        }],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true, title: { display: true, text: 'Article mentions' } } },
      },
    });
  }

  function renderCategoryChart() {
    if (!categoryCanvas || !nlpCategories.length) return;

    categoryChart = new Chart(categoryCanvas, {
      type: 'bar',
      data: {
        labels: nlpCategories.map(c => c.category_name),
        datasets: [{
          label: 'Articles',
          data: nlpCategories.map(c => c.article_count),
          backgroundColor: nlpCategories.map(c => {
            const score = c.avg_sentiment_score ?? 0;
            if (score > 0.1) return COLORS.positive + 'CC';
            if (score < -0.1) return COLORS.negative + 'CC';
            return COLORS.neutral + 'CC';
          }),
        }],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true, title: { display: true, text: 'Articles' } } },
      },
    });
  }

  function handleDaysChange(event: Event) {
    days = parseInt((event.target as HTMLSelectElement).value);
    loadData();
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleString();
  }

  onMount(() => { loadData(); });
  onDestroy(() => { destroyCharts(); });
</script>

<div class="dashboard">
  <!-- Controls -->
  <div class="controls">
    <h2 class="text-xl font-semibold text-gray-900">Analytics Dashboard</h2>
    <select on:change={handleDaysChange} value={days} class="select">
      <option value={7}>Last 7 days</option>
      <option value={30}>Last 30 days</option>
      <option value={90}>Last 90 days</option>
      <option value={365}>Last year</option>
    </select>
  </div>

  {#if error}
    <div class="error-banner">{error}</div>
  {/if}

  {#if loading}
    <div class="loading">
      <div class="spinner"></div>
      <p class="text-gray-600">Loading analytics...</p>
    </div>
  {:else}
    <div class="grid-2">
      <!-- Sentiment Trends -->
      <div class="card">
        <h3 class="text-lg font-semibold text-gray-900">Sentiment Trends</h3>
        {#if trends.length}
          <canvas bind:this={trendCanvas}></canvas>
        {:else}
          <p class="text-sm text-gray-500 empty">No trend data available</p>
        {/if}
      </div>

      <!-- Source Comparison -->
      <div class="card">
        <h3 class="text-lg font-semibold text-gray-900">Source Comparison</h3>
        {#if sources.length}
          <canvas bind:this={sourceCanvas}></canvas>
        {:else}
          <p class="text-sm text-gray-500 empty">No source data available</p>
        {/if}
      </div>

      <!-- Top Entities -->
      <div class="card">
        <h3 class="text-lg font-semibold text-gray-900">Top Entities</h3>
        <p class="text-xs text-gray-500">Color: green = positive, red = negative, blue = neutral sentiment</p>
        {#if entities.length}
          <canvas bind:this={entityCanvas}></canvas>
        {:else}
          <p class="text-sm text-gray-500 empty">No entity data available</p>
        {/if}
      </div>

      <!-- NLP Categories -->
      <div class="card">
        <h3 class="text-lg font-semibold text-gray-900">GCP NL Categories</h3>
        <p class="text-xs text-gray-500">ML-classified content taxonomy from GCP Natural Language</p>
        {#if nlpCategories.length}
          <canvas bind:this={categoryCanvas}></canvas>
        {:else}
          <p class="text-sm text-gray-500 empty">No category data available</p>
        {/if}
      </div>
    </div>

    <!-- Pipeline Health -->
    <div class="card" style="margin-top: 1.5rem;">
      <h3 class="text-lg font-semibold text-gray-900">Pipeline Health</h3>
      {#if pipeline.length}
        <div class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Started</th>
                <th>Duration</th>
                <th>Fetched</th>
                <th>Ingested</th>
                <th>Crawl OK</th>
                <th>Crawl Fail</th>
              </tr>
            </thead>
            <tbody>
              {#each pipeline as run}
                <tr>
                  <td>{formatDate(run.started_at)}</td>
                  <td>{run.duration_seconds.toFixed(1)}s</td>
                  <td>{run.articles_fetched}</td>
                  <td>{run.articles_ingested}</td>
                  <td>{run.crawl_successful ?? '-'}</td>
                  <td>{run.crawl_failed ?? '-'}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {:else}
        <p class="text-sm text-gray-500 empty">No pipeline data available</p>
      {/if}
    </div>
  {/if}
</div>

<style>
  .dashboard { padding: 0; }

  .controls {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
  }

  .select {
    padding: 0.5rem 1rem;
    border: 1px solid #d1d5db;
    border-radius: 0.375rem;
    background: white;
    font-size: 0.875rem;
    cursor: pointer;
  }

  .error-banner {
    background: #fef2f2;
    border: 1px solid #fca5a5;
    color: #b91c1c;
    padding: 0.75rem 1rem;
    border-radius: 0.375rem;
    margin-bottom: 1.5rem;
  }

  .loading {
    text-align: center;
    padding: 3rem 0;
  }

  .spinner {
    width: 3rem;
    height: 3rem;
    border: 2px solid transparent;
    border-bottom-color: #2563eb;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin: 0 auto 1rem;
  }

  @keyframes spin { to { transform: rotate(360deg); } }

  .grid-2 {
    display: grid;
    grid-template-columns: 1fr;
    gap: 1.5rem;
  }

  @media (min-width: 768px) {
    .grid-2 { grid-template-columns: 1fr 1fr; }
  }

  .card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 0.5rem;
    padding: 1.25rem;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
  }

  .card h3 { margin-bottom: 0.75rem; }

  .empty {
    text-align: center;
    padding: 2rem 0;
  }

  .table-wrapper { overflow-x: auto; }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
  }

  th, td {
    padding: 0.5rem 0.75rem;
    text-align: left;
    border-bottom: 1px solid #e5e7eb;
  }

  th {
    font-weight: 600;
    color: #374151;
    background: #f9fafb;
  }

  td { color: #6b7280; }
</style>
