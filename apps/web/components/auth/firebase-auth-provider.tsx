"use client";

import {
  GoogleAuthProvider,
  createUserWithEmailAndPassword,
  onIdTokenChanged,
  sendEmailVerification,
  signInAnonymously,
  signInWithEmailAndPassword,
  signInWithPopup,
  linkWithPopup,
  signOut as firebaseSignOut,
  type User,
} from "firebase/auth";
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { firebaseConfigured, getFirebaseAuth } from "@/lib/firebase";

type FirebaseAuthContextValue = {
  configured: boolean;
  loading: boolean;
  user: User | null;
  continueAsGuest: () => Promise<User>;
  signInWithGoogle: () => Promise<User>;
  upgradeGuestWithGoogle: () => Promise<User>;
  signInWithEmail: (email: string, password: string) => Promise<User>;
  createEmailAccount: (email: string, password: string) => Promise<User>;
  signOut: () => Promise<void>;
};

const FirebaseAuthContext = createContext<FirebaseAuthContextValue | null>(null);

export function FirebaseAuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(firebaseConfigured);
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    if (!firebaseConfigured) return;
    return onIdTokenChanged(getFirebaseAuth(), (nextUser) => {
      setUser(nextUser);
      setLoading(false);
    });
  }, []);

  const value = useMemo<FirebaseAuthContextValue>(
    () => ({
      configured: firebaseConfigured,
      loading,
      user,
      async continueAsGuest() {
        return (await signInAnonymously(getFirebaseAuth())).user;
      },
      async signInWithGoogle() {
        return (await signInWithPopup(getFirebaseAuth(), new GoogleAuthProvider())).user;
      },
      async upgradeGuestWithGoogle() {
        const currentUser = getFirebaseAuth().currentUser;
        if (!currentUser?.isAnonymous) {
          throw new Error("Only an anonymous account can be upgraded");
        }
        return (await linkWithPopup(currentUser, new GoogleAuthProvider())).user;
      },
      async signInWithEmail(email, password) {
        return (await signInWithEmailAndPassword(getFirebaseAuth(), email, password)).user;
      },
      async createEmailAccount(email, password) {
        const created = await createUserWithEmailAndPassword(
          getFirebaseAuth(),
          email,
          password,
        );
        await sendEmailVerification(created.user);
        return created.user;
      },
      async signOut() {
        await firebaseSignOut(getFirebaseAuth());
      },
    }),
    [loading, user],
  );

  return <FirebaseAuthContext.Provider value={value}>{children}</FirebaseAuthContext.Provider>;
}

export function useFirebaseAuth(): FirebaseAuthContextValue {
  const value = useContext(FirebaseAuthContext);
  if (!value) throw new Error("useFirebaseAuth must be used inside FirebaseAuthProvider");
  return value;
}
