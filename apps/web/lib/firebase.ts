"use client";

import { getApp, getApps, initializeApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
};

export const firebaseConfigured = Boolean(
  firebaseConfig.apiKey &&
    firebaseConfig.appId &&
    firebaseConfig.authDomain &&
    firebaseConfig.projectId,
);

let authInstance: Auth | undefined;

export function getFirebaseAuth(): Auth {
  if (!firebaseConfigured) {
    throw new Error("Firebase Authentication is not configured for this web build.");
  }
  const app = getApps().length ? getApp() : initializeApp(firebaseConfig);
  authInstance ??= getAuth(app);
  return authInstance;
}
