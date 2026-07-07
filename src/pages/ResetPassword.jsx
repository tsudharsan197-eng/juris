import { useState } from "react";
import { Link } from "react-router-dom";
import Button from "../components/Button.jsx";
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
    <AuthLayout eyebrow="New password" title="Set a new secure password." aside={<ResetCopy />}>
      <form className="auth-form" onSubmit={handleSubmit}>
        <label>
          New password
          <input name="password" type="password" autoComplete="new-password" minLength="8" required />
        </label>
        <label>
          Confirm password
          <input name="confirm" type="password" autoComplete="new-password" minLength="8" required />
        </label>
        <Button type="submit">Update Password</Button>
        {status && <p className="form-status">{status}</p>}
      </form>
      <p className="auth-switch">
        Back to <Link to="/sign-in">sign in</Link>
      </p>
    </AuthLayout>
  );
}

function ResetCopy() {
  return <p>Use this route as the destination for Supabase recovery links.</p>;
}
