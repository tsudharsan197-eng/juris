import { useState } from "react";
import { Link } from "react-router-dom";
import Button from "../components/Button.jsx";
import PasswordField from "../components/PasswordField.jsx";
import AuthLayout from "./AuthLayout.jsx";
import { signUpWithEmail } from "../lib/supabase.js";

export default function CreateAccount() {
  const [status, setStatus] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const { error } = await signUpWithEmail(
      form.get("name"),
      form.get("email"),
      form.get("password"),
    );
    setStatus(error ? error.message : "Account created. Check your email to confirm access.");
  }

  return (
    <AuthLayout
      eyebrow="Create account"
      title="Start decoding legal documents."
      mobileTitle="Create your account."
      mobileDescription="Set up secure access to your Juris legal workspace."
      aside={<AuthAside />}
    >
      <form className="auth-form" onSubmit={handleSubmit}>
        <label>
          Name
          <input name="name" type="text" autoComplete="name" required />
        </label>
        <label>
          Email
          <input name="email" type="email" autoComplete="email" required />
        </label>
        <PasswordField
          name="password"
          label="Password"
          autoComplete="new-password"
          minLength="8"
          required
        />
        <Button type="submit">Create Account</Button>
        <div className={`form-status-slot${status ? " has-status" : ""}`} aria-live="polite">
          {status && <p className="form-status">{status}</p>}
        </div>
      </form>
      <p className="auth-switch">
        <span>Already have an account?</span> <Link to="/sign-in">Sign in</Link>
      </p>
    </AuthLayout>
  );
}

function AuthAside() {
  return (
    <>
      <div className="aside-metric">
        <strong>AI-ready</strong>
        <span>Summaries, clauses, risks, chat, and comparison workflows.</span>
      </div>
      <div className="aside-lines">
        <span />
        <span />
        <span />
      </div>
      <p>Prepared for Supabase Auth, secure session handling, and Neon/Supabase data layers.</p>
    </>
  );
}
