import { initializeApp } from "firebase/app";
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signOut,
  onAuthStateChanged,
  type User
} from "firebase/auth";
import { writable } from "svelte/store";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "demo-api-key",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "demo-project.firebaseapp.com",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "demo-project",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "demo-app-id"
};

let app: any = null;
let auth: any = null;

try {
  app = initializeApp(firebaseConfig);
  auth = getAuth(app);
  console.log("Firebase initialized successfully");
} catch (error) {
  console.warn("Firebase initialization failed:", error);
  console.log("Running in demo mode - authentication disabled");
}

export { auth };

const googleProvider = new GoogleAuthProvider();

export const userStore = writable<User | null>(null);

if (auth) {
  onAuthStateChanged(auth, (u) => userStore.set(u));
} else {
  // Demo mode - no authentication
  userStore.set(null);
}

export async function loginWithGoogle() {
  if (!auth) {
    alert("Firebase authentication not configured. Please set up Firebase credentials.");
    return;
  }
  await signInWithPopup(auth, googleProvider);
}

export async function logout() {
  if (!auth) return;
  await signOut(auth);
}

export async function getIdToken(): Promise<string | null> {
  if (!auth?.currentUser) return null;
  return await auth.currentUser.getIdToken();
}
