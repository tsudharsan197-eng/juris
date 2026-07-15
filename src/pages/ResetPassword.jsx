import { useState } from "react";
import { Link } from "react-router-dom";
import Button from "../components/Button.jsx";
import PasswordField from "../components/PasswordField.jsx";
import AuthLayout from "./AuthLayout.jsx";
import { updatePassword } from "../lib/supabase.js";

export default function ResetPassword() {
  const [status, setStatus] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const password = form.get("password");
    const confirm = form.get("confirm");
    if (password !== confirm) {
      setStatus("Passwords do not match.");
      return;
    }
    const { error } = await updatePassword(password);
    setStatus(error ? error.message : "Password updated. You can now sign in.");
  }

  return (
    <AuthLayout
      eyebrow="New password"
      title="Set a new secure password."
      mobileTitle="Set a new password."
      mobileDescription="Choose at least eight characters for your new account password."
      aside={<ResetCopy />}
    >
      <form className="auth-form" onSubmit={handleSubmit}>
        <PasswordField
          name="password"
          label="New password"
          autoComplete="new-password"
          minLength="8"
          required
        />
        <PasswordField
          name="confirm"
          label="Confirm password"
          autoComplete="new-password"
          minLength="8"
          required
        />
        <Button type="submit">Update Password</Button>
        <div className={`form-status-slot${status ? " has-status" : ""}`} aria-live="polite">
          {status && <p className="form-status">{status}</p>}
        </div>
      </form>
      <p className="auth-switch">
        <span>Back to account access.</span> <Link to="/sign-in">Sign in</Link>
      </p>
    </AuthLayout>
  );
}

function ResetCopy() {
  return <p>Use this route as the destination for Supabase recovery links.</p>;
}
