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

## 🛠️ Project Structure

- `src/` — Svelte app source code
- `public/` — Static assets
- `firebase.json` — Firebase Hosting config

## 📝 Documentation
- See the root `README.md` and `docs/PROJECT_STRUCTURE.md` for backend and deployment details.

## 🚀 Production URL
https://aifeelnews-front.firebaseapp.com
