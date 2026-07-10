import { useState } from "react";
import { Link } from "react-router-dom";
import { AnimatePresence, motion, useMotionValueEvent, useScroll } from "framer-motion";
import { FileUp, Files, LogIn, LogOut, Menu, X } from "lucide-react";
import Button from "./Button.jsx";
import ThemeToggle from "./ThemeToggle.jsx";
import { useAuth } from "./AuthProvider.jsx";
import { signOut } from "../lib/supabase.js";

export default function Navbar() {
  const { user, isSignedIn } = useAuth();
  const { scrollY } = useScroll();
  const [compact, setCompact] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const accountLabel = user?.user_metadata?.name || user?.email;

  useMotionValueEvent(scrollY, "change", (value) => {
    const previous = scrollY.getPrevious() ?? 0;
    setCompact(value > 36);
    setHidden(value > 140 && value > previous);
  });

  async function handleSignOut() {
    await signOut();
    window.location.assign("/");
  }

  return (
    <header className={`navbar-wrap ${compact ? "compact" : ""} ${hidden ? "nav-hidden" : ""}`}>
      <motion.nav className="navbar" aria-label="Main navigation" layout>
        <Link className="logo" to="/">
          <span>Juris.</span>
          <i aria-hidden="true" />
        </Link>
        <div className="nav-status" aria-hidden="true">AI / LEGAL INTELLIGENCE / 2026</div>
        <div className="nav-actions desktop-nav-actions">
          <ThemeToggle />
          <Button to="/upload-document" variant="ghost">
            <FileUp aria-hidden="true" size={16} /> Upload
          </Button>
          {isSignedIn ? (
            <>
              <Button to="/documents" variant="ghost">
                <Files aria-hidden="true" size={16} /> Documents
              </Button>
              <span className="account-pill" title={accountLabel}>
                {accountLabel}
              </span>
              <Button type="button" variant="primary" onClick={handleSignOut}>
                <LogOut aria-hidden="true" size={16} /> Sign Out
              </Button>
            </>
          ) : (
            <>
              <Button to="/sign-in" variant="ghost">
                <LogIn aria-hidden="true" size={16} /> Sign In
              </Button>
              <Button to="/create-account" variant="primary">
                Create Account
              </Button>
            </>
          )}
        </div>
        <div className="mobile-nav-actions">
          <ThemeToggle />
          <button
            className="mobile-menu-toggle"
            type="button"
            aria-label={menuOpen ? "Close navigation" : "Open navigation"}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
          >
            {menuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </motion.nav>
      <AnimatePresence>
        {menuOpen && (
          <motion.div
            className="mobile-nav-panel"
            initial={{ opacity: 0, y: -12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
          >
            <Link to="/upload-document" onClick={() => setMenuOpen(false)}><FileUp size={17} /> Upload</Link>
            {isSignedIn ? (
              <>
                <Link to="/documents" onClick={() => setMenuOpen(false)}><Files size={17} /> Documents</Link>
                <span className="mobile-account">{accountLabel}</span>
                <button type="button" onClick={handleSignOut}><LogOut size={17} /> Sign Out</button>
              </>
            ) : (
              <>
                <Link to="/sign-in" onClick={() => setMenuOpen(false)}><LogIn size={17} /> Sign In</Link>
                <Link className="mobile-primary" to="/create-account" onClick={() => setMenuOpen(false)}>Create Account</Link>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
