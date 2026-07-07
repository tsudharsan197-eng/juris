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
    <AuthLayout eyebrow="Reset access" title="Recover your Juris account." aside={<ResetAside />}>
      <form className="auth-form" onSubmit={handleSubmit}>
        <label>
          Email
          <input name="email" type="email" autoComplete="email" required />
        </label>
        <Button type="submit">Send Reset Link</Button>
        {status && <p className="form-status">{status}</p>}
      </form>
      <p className="auth-switch">
        Remembered it? <Link to="/sign-in">Sign in</Link>
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
