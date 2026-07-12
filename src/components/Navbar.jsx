import { useEffect, useRef, useState } from "react";
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
  const menuScrollPosition = useRef(0);
  const restoreMenuScroll = useRef(true);
  const accountLabel = user?.user_metadata?.name || user?.email;

  useMotionValueEvent(scrollY, "change", (value) => {
    const previous = scrollY.getPrevious() ?? 0;
    setCompact(value > 36);
    setHidden(value > 140 && value > previous);
  });

  useEffect(() => {
    if (!menuOpen) return undefined;
    menuScrollPosition.current = window.scrollY;
    document.documentElement.classList.add("mobile-menu-open");
    document.body.classList.add("mobile-menu-open");
    return () => {
      document.documentElement.classList.remove("mobile-menu-open");
      document.body.classList.remove("mobile-menu-open");
      const top = restoreMenuScroll.current ? menuScrollPosition.current : 0;
      window.scrollTo({ top, left: 0, behavior: "auto" });
      window.requestAnimationFrame(() => {
        window.dispatchEvent(new CustomEvent("juris:restore-scroll", { detail: top }));
      });
    };
  }, [menuOpen]);

  function closeMenuForNavigation() {
    restoreMenuScroll.current = false;
    setMenuOpen(false);
  }

  async function handleSignOut() {
    restoreMenuScroll.current = false;
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
            onClick={() => {
              restoreMenuScroll.current = true;
              setMenuOpen((open) => !open);
            }}
          >
            {menuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </motion.nav>
      <AnimatePresence>
        {menuOpen && (
          <motion.div
            className="mobile-nav-panel"
            variants={mobileMenu}
            initial="hidden"
            animate="visible"
            exit="hidden"
          >
            <motion.div className="mobile-nav-item" variants={mobileMenuItem}>
              <Link to="/upload-document" onClick={closeMenuForNavigation}><FileUp size={17} /> Upload</Link>
            </motion.div>
            {isSignedIn ? (
              <>
                <motion.div className="mobile-nav-item" variants={mobileMenuItem}>
                  <Link to="/documents" onClick={closeMenuForNavigation}><Files size={17} /> Documents</Link>
                </motion.div>
                <motion.div className="mobile-nav-item" variants={mobileMenuItem}>
                  <span className="mobile-account">{accountLabel}</span>
                </motion.div>
                <motion.div className="mobile-nav-item" variants={mobileMenuItem}>
                  <button type="button" onClick={handleSignOut}><LogOut size={17} /> Sign Out</button>
                </motion.div>
              </>
            ) : (
              <>
                <motion.div className="mobile-nav-item" variants={mobileMenuItem}>
                  <Link to="/sign-in" onClick={closeMenuForNavigation}><LogIn size={17} /> Sign In</Link>
                </motion.div>
                <motion.div className="mobile-nav-item" variants={mobileMenuItem}>
                  <Link className="mobile-primary" to="/create-account" onClick={closeMenuForNavigation}>Create Account</Link>
                </motion.div>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}

const mobileMenu = {
  hidden: {
    clipPath: "inset(0 0 100% 0)",
    transition: { duration: .32, ease: [.55, 0, .45, 1], when: "afterChildren", staggerChildren: .025, staggerDirection: -1 },
  },
  visible: {
    clipPath: "inset(0 0 0% 0)",
    transition: { duration: .46, ease: [.25, .8, .25, 1], when: "beforeChildren", staggerChildren: .055 },
  },
};

const mobileMenuItem = {
  hidden: { y: 24, opacity: 0, clipPath: "inset(0 0 100% 0)" },
  visible: { y: 0, opacity: 1, clipPath: "inset(0 0 0% 0)", transition: { duration: .38, ease: [.25, .8, .25, 1] } },
};
