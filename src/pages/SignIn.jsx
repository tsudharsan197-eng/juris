import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Button from "../components/Button.jsx";
import AuthLayout from "./AuthLayout.jsx";
import { signInWithEmail } from "../lib/supabase.js";

export default function SignIn() {
  const navigate = useNavigate();
  const [status, setStatus] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const { error } = await signInWithEmail(form.get("email"), form.get("password"));
    if (error) {
      setStatus(error.message);
      return;
    }
    setStatus("Signed in successfully.");
    navigate("/");
  }

  return (
    <AuthLayout eyebrow="Sign in" title="Return to your legal workspace." aside={<SignInAside />}>
      <form className="auth-form" onSubmit={handleSubmit}>
        <label>
          Email
          <input name="email" type="email" autoComplete="email" required />
        </label>
        <label>
          Password
          <input name="password" type="password" autoComplete="current-password" required />
        </label>
        <div className="form-row">
          <Link to="/forgot-password">Forgot password?</Link>
        </div>
        <Button type="submit">Sign In</Button>
        {status && <p className="form-status">{status}</p>}
      </form>
      <p className="auth-switch">
        New to Juris? <Link to="/create-account">Create account</Link>
      </p>
    </AuthLayout>
  );
}

function SignInAside() {
  return (
    <>
      <div className="aside-metric">
        <strong>Risk-first</strong>
        <span>Review contracts with extracted obligations and clause-backed answers.</span>
      </div>
      <div className="mini-doc">
        <i />
        <i />
        <i />
        <b>Clause 11 flagged</b>
      </div>
    </>
  );
}
