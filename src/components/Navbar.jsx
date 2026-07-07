import { Link } from "react-router-dom";
import Button from "./Button.jsx";
import ThemeToggle from "./ThemeToggle.jsx";
import { useAuth } from "./AuthProvider.jsx";
import { signOut } from "../lib/supabase.js";

export default function Navbar() {
  const { user, isSignedIn } = useAuth();
  const accountLabel = user?.user_metadata?.name || user?.email;

  async function handleSignOut() {
    await signOut();
    window.location.assign("/");
  }

  return (
    <header className="navbar-wrap">
      <nav className="navbar" aria-label="Main navigation">
        <Link className="logo" to="/">
          Juris.
        </Link>
        <div className="nav-actions">
          <ThemeToggle />
          <Button to="/upload-document" variant="ghost">
            Upload
          </Button>
          {isSignedIn ? (
            <>
              <Button to="/documents" variant="ghost">
                Documents
              </Button>
              <span className="account-pill" title={accountLabel}>
                {accountLabel}
              </span>
              <Button type="button" variant="primary" onClick={handleSignOut}>
                Sign Out
              </Button>
            </>
          ) : (
            <>
              <Button to="/sign-in" variant="ghost">
                Sign In
              </Button>
              <Button to="/create-account" variant="primary">
                Create Account
              </Button>
            </>
          )}
        </div>
      </nav>
    </header>
  );
}
