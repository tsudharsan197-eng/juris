import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const hasSupabaseConfig = Boolean(supabaseUrl && supabaseAnonKey);

export const supabase = hasSupabaseConfig
  ? createClient(supabaseUrl, supabaseAnonKey)
  : null;

export async function signInWithEmail(email, password) {
  if (!supabase) return { error: new Error("Supabase is not configured.") };
  return supabase.auth.signInWithPassword({ email, password });
}

export async function signUpWithEmail(name, email, password) {
  if (!supabase) return { error: new Error("Supabase is not configured.") };
  return supabase.auth.signUp({
    email,
    password,
    options: {
      data: { name },
      emailRedirectTo: `${window.location.origin}/sign-in`,
    },
  });
}

export async function requestPasswordReset(email) {
  if (!supabase) return { error: new Error("Supabase is not configured.") };
  return supabase.auth.resetPasswordForEmail(email, {
    redirectTo: `${window.location.origin}/reset-password`,
  });
}

export async function updatePassword(password) {
  if (!supabase) return { error: new Error("Supabase is not configured.") };
  return supabase.auth.updateUser({ password });
}

export async function getCurrentSession() {
  if (!supabase) return { data: null, error: new Error("Supabase is not configured.") };
  return supabase.auth.getSession();
}

export async function signOut() {
  if (!supabase) return { error: new Error("Supabase is not configured.") };
  return supabase.auth.signOut();
}
