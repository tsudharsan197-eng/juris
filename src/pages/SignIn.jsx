import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Button from "../components/Button.jsx";
import PasswordField from "../components/PasswordField.jsx";
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
    <AuthLayout
      eyebrow="Sign in"
      title="Return to your legal workspace."
      mobileTitle="Sign in to Juris."
      mobileDescription="Access your documents and continue your legal analysis."
      aside={<SignInAside />}
    >
      <form className="auth-form" onSubmit={handleSubmit}>
        <label>
          Email
          <input name="email" type="email" autoComplete="email" required />
        </label>
        <PasswordField
          name="password"
          label="Password"
          autoComplete="current-password"
          required
        />
        <div className="form-row">
          <Link to="/forgot-password">Forgot password?</Link>
        </div>
        <Button type="submit">Sign In</Button>
        <div className={`form-status-slot${status ? " has-status" : ""}`} aria-live="polite">
          {status && <p className="form-status">{status}</p>}
        </div>
      </form>
      <p className="auth-switch">
        <span>New to Juris?</span> <Link to="/create-account">Create account</Link>
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
