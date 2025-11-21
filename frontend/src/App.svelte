<script lang="ts">
  import { onMount } from 'svelte';
  import { userStore, loginWithGoogle, logout } from './lib/firebase';
  import { fetchLatestArticles, type ArticleDto } from './lib/api';

  let articles: ArticleDto[] = [];
  let loading = true;
  let error = '';

  async function loadArticles() {
    try {
      loading = true;
      articles = await fetchLatestArticles(40);
    } catch (e) {
      error = 'Failed to load articles';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    loadArticles();
  });

  function getSentimentColor(label?: string): string {
    if (!label) return 'text-gray-500';
    switch (label.toLowerCase()) {
      case 'positive': return 'text-green-600';
      case 'negative': return 'text-red-600';
      case 'neutral': return 'text-blue-600';
      default: return 'text-gray-500';
    }
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString();
  }
</script>

<div class="min-h-screen bg-gray-50">
  <!-- Header -->
  <header class="bg-white shadow-sm border-b">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between items-center h-16">
        <h1 class="text-2xl font-bold text-gray-900">aiFeelNews</h1>

        <div class="flex items-center space-x-4">
          {#if $userStore}
            <span class="text-sm text-gray-600">Welcome, {$userStore.email}</span>
            <button
              on:click={logout}
              class="bg-red-600 text-white px-4 py-2 rounded-md text-sm hover:bg-red-700"
            >
              Logout
            </button>
          {:else}
            <button
              on:click={loginWithGoogle}
              class="bg-blue-600 text-white px-4 py-2 rounded-md text-sm hover:bg-blue-700"
            >
              Login with Google
            </button>
          {/if}
        </div>
      </div>
    </div>
  </header>

  <!-- Main Content -->
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    {#if error}
      <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-6">
        {error}
      </div>
    {/if}

    {#if loading}
      <div class="text-center py-12">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
        <p class="mt-4 text-gray-600">Loading latest articles...</p>
      </div>
    {:else}
      <div class="mb-6">
        <h2 class="text-xl font-semibold text-gray-900">Latest Articles ({articles.length})</h2>
        <p class="text-gray-600">Recent news with sentiment analysis</p>
      </div>

      <div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {#each articles as article}
          <div class="bg-white rounded-lg shadow-sm border p-6 hover:shadow-md transition-shadow">
            <!-- Source -->
            <div class="flex items-center justify-between mb-3">
              <span class="text-xs font-medium text-blue-600 bg-blue-100 px-2 py-1 rounded">
                {article.source.name}
              </span>
              <span class="text-xs text-gray-500">{formatDate(article.published_at)}</span>
            </div>

            <!-- Title -->
            <h3 class="text-lg font-semibold text-gray-900 mb-2 line-clamp-2">
              {article.title}
            </h3>

            <!-- Description -->
            {#if article.description}
              <p class="text-gray-600 text-sm mb-3 line-clamp-3">
                {article.description}
              </p>
            {/if}

            <!-- Sentiment -->
            {#if article.latest_sentiment}
              <div class="flex items-center justify-between mb-4">
                <span class="text-xs text-gray-500">Sentiment:</span>
                <span class="text-sm font-medium {getSentimentColor(article.latest_sentiment.label)}">
                  {article.latest_sentiment.label} ({article.latest_sentiment.score.toFixed(2)})
                </span>
              </div>
            {/if}

            <!-- Actions -->
            <div class="flex items-center justify-between">
              <a
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                class="text-blue-600 hover:text-blue-800 text-sm font-medium"
              >
                Read Article →
              </a>

              {#if $userStore}
                <button class="text-gray-400 hover:text-gray-600">
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"></path>
                  </svg>
                </button>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </main>
</div>

<style>
  .line-clamp-2 {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .line-clamp-3 {
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
</style>
