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
4. Build for production:
   ```bash
   npm run build
   ```
5. Deploy to Firebase Hosting:
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

## 🛠️ Project Structure

- `src/` — Svelte app source code
- `public/` — Static assets
- `firebase.json` — Firebase Hosting config

## 📝 Documentation
- See the root `README.md` and `docs/PROJECT_STRUCTURE.md` for backend and deployment details.

## 🚀 Production URL
https://aifeelnews-front.web.app/
