# aiFeelNews Frontend (Svelte + Vite)

This is the frontend for aiFeelNews, built with Svelte, TypeScript, and Vite. It connects to the FastAPI backend and uses Firebase Authentication (Google provider).

## ⚡ Quick Start

1. Copy `.env.example` to `.env` and fill in your Firebase and API credentials.
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run the dev server:
   ```bash
   npm run dev
   ```
4. Run the unit tests:
   ```bash
   npm test            # single run (what CI runs)
   npm run test:watch  # watch mode
   ```
5. Build for production:
   ```bash
   npm run build
   ```
6. Deploy to Firebase Hosting:
   ```bash
   npx firebase deploy --only hosting
   ```

## 🔐 Security Notice
**Never commit your Firebase or Google Cloud service account JSON files to the repository.**
Service account credentials are only needed for backend deployment and should be managed via Google Secret Manager.

## 🌐 Environment Variables
See `.env.example` for required variables:

- `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, etc. — from your Firebase project
- `VITE_API_BASE_URL` — backend API URL

## 🎨 UI notes

- **Dark-first theme.** The app ships dark by default (a first visit always sees the designed dark look — it deliberately does *not* follow the OS `prefers-color-scheme`). A header toggle switches to light and the choice persists in `localStorage` (`src/lib/theme.ts`).
- **Privacy by design, no cookies.** Firebase stores its auth token in `localStorage`/IndexedDB, not cookies, and the app sets no tracking cookies — so there is no cookie banner. The footer states this and links to an in-app **Privacy** page (`src/lib/Privacy.svelte`) that describes what data the platform handles.
- **3-page SPA.** A lightweight state machine (`articles | analytics | bookmarks`, plus the public privacy page) — no SvelteKit/router. The wordmark is a home link.

## 🧪 Testing

Unit tests run on Vitest + jsdom + Testing Library, co-located with the
modules they cover (`src/lib/*.test.ts`):

- `api.test.ts` — the backend contract: query-string assembly and status-code
  semantics (409 → silent success, 401 → `AuthExpiredError`, 404 → silent
  delete), plus the Postgres `Decimal`-string → `number` coercion
- `sentiment.test.ts` — `describeSentiment` / `magnitudeTier` branches,
  including the calibrated magnitude thresholds
- `bookmarkStore.test.ts` — Set/Map consistency across add, remove, hydrate, reset
- `theme.test.ts` — dark-first default, `localStorage` persistence, `data-theme`
- `Pagination.test.ts` — component rendering: page math, prev/next enablement

`npm test` runs the suite once — CI does the same in `frontend-check.yml`
after the type-check. Config lives in `vitest.config.ts` (extends
`vite.config.ts` so components compile exactly as in the real build) and
`vitest-setup.ts` (jest-dom matchers).

## 🛠️ Project Structure

- `src/` — Svelte app source code (tests co-located as `src/lib/*.test.ts`)
- `public/` — Static assets
- `firebase.json` — Firebase Hosting config
- `vitest.config.ts`, `vitest-setup.ts` — test configuration

## 📝 Documentation
- See the root `README.md` and `docs/PROJECT_STRUCTURE.md` for backend and deployment details.

## 🚀 Production URL
https://aifeelnews-front.web.app/
