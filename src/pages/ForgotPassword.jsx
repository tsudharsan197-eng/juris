import { useState } from "react";
import { Link } from "react-router-dom";
import Button from "../components/Button.jsx";
import AuthLayout from "./AuthLayout.jsx";
import { requestPasswordReset } from "../lib/supabase.js";

export default function ForgotPassword() {
  const [status, setStatus] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const { error } = await requestPasswordReset(form.get("email"));
    setStatus(error ? error.message : "Password reset link sent if that email exists.");
  }

  return (
    <AuthLayout
      eyebrow="Reset access"
      title="Recover your Juris account."
      mobileTitle="Recover your account."
      mobileDescription="We will send a secure recovery link to your email address."
      aside={<ResetAside />}
    >
      <form className="auth-form" onSubmit={handleSubmit}>
        <label>
          Email
          <input name="email" type="email" autoComplete="email" required />
        </label>
        <Button type="submit">Send Reset Link</Button>
        <div className={`form-status-slot${status ? " has-status" : ""}`} aria-live="polite">
          {status && <p className="form-status">{status}</p>}
        </div>
      </form>
      <p className="auth-switch">
        <span>Remembered it?</span> <Link to="/sign-in">Sign in</Link>
      </p>
    </AuthLayout>
  );
}

function ResetAside() {
  return (
    <p>
      Supabase will email a secure recovery link and redirect users back to the Juris reset
      password route.
    </p>
  );
}
