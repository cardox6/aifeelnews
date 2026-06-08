<script lang="ts">
  // A short, honest privacy statement that reflects what the app actually does.
  // This is NOT corporate boilerplate — every claim maps to the real
  // architecture (data minimisation, TTL, EU region, no tracking).
  const lastUpdated = "June 2026";
</script>

<section class="privacy" aria-labelledby="privacy-title">
  <div class="page-head">
    <h1 class="page-title" id="privacy-title">Privacy</h1>
    <p class="page-subtitle">
      What we collect, why, and what we deliberately don't do. Last updated {lastUpdated}.
    </p>
  </div>

  <div class="prose">
    <p>
      aiFeelNews is a university project that analyses the sentiment of news
      articles. This page describes how it handles data. It is written to be
      accurate, not to cover a business we don't run.
    </p>

    <h2>What we collect</h2>
    <ul>
      <li>
        <strong>Your email address</strong>, when you sign in. We use it only to
        identify your account and attach your bookmarks to it.
      </li>
      <li>
        <strong>Your bookmarks</strong> — the articles you save while signed in.
      </li>
    </ul>
    <p>
      We do <strong>not</strong> collect names, payment details, location, or
      browsing history, and we do not build advertising or behavioural profiles.
    </p>

    <h2>Sign-in</h2>
    <p>
      Authentication is handled by <strong>Firebase Authentication</strong>
      (Google sign-in). Your session token is stored locally in your browser
      (IndexedDB / local storage), <strong>not</strong> in cookies, and is sent
      to our API only to authorise your own requests.
    </p>

    <h2>Cookies &amp; tracking</h2>
    <p>
      This site sets <strong>no cookies</strong> and uses <strong>no
      third-party analytics, advertising, or tracking</strong>. That's why you
      won't see a cookie-consent banner — there's nothing to consent to.
    </p>

    <h2>Article content &amp; data minimisation</h2>
    <p>
      We ingest article metadata from <strong>Mediastack</strong> and, where
      permitted by a site's <code>robots.txt</code>, crawl the original article
      to analyse it. We <strong>do not keep full article bodies</strong>:
      extracted text is truncated to 1,024 characters and automatically deleted
      after 7 days by a time-to-live (TTL) cleanup job. Sentiment, entities and
      categories are produced by <strong>Google Cloud Natural Language</strong>.
    </p>

    <h2>Where your data lives</h2>
    <p>
      Data is stored on Google Cloud in the <strong>europe-west1 (EU)</strong>
      region.
    </p>

    <h2>Your choices</h2>
    <ul>
      <li>You can remove any bookmark at any time while signed in.</li>
      <li>
        To have your account email and bookmarks deleted, contact the project
        maintainer via the
        <a href="https://github.com/cardox6/aifeelnews" target="_blank" rel="noopener noreferrer">
          project repository</a>.
      </li>
    </ul>

    <p class="text-ter">
      This is a student project and not a commercial service; this statement is
      a good-faith description of its data handling, not a legal contract.
    </p>
  </div>
</section>

<style>
  .privacy {
    max-width: 760px;
  }
  .prose {
    color: var(--text-sec);
    line-height: 1.7;
  }
  .prose h2 {
    color: var(--text-pri);
    font-size: 1.1rem;
    margin: var(--sp-6) 0 var(--sp-2);
  }
  .prose ul {
    padding-left: 1.25rem;
    margin: var(--sp-2) 0;
  }
  .prose li {
    margin: 0.35rem 0;
  }
  .prose code {
    font-family: var(--font-mono);
    font-size: 0.85em;
    padding: 0.1em 0.35em;
    border-radius: var(--r-sm);
    background: var(--bg-raised);
  }
  .prose a {
    color: var(--accent);
  }
</style>
