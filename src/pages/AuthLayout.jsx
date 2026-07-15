import { Link } from "react-router-dom";
import ThemeToggle from "../components/ThemeToggle.jsx";

export default function AuthLayout({
  eyebrow,
  title,
  mobileTitle = title,
  mobileDescription,
  mobileTrust = "Secure access. Your legal documents remain private and user-scoped.",
  children,
  aside,
}) {
  return (
    <main className="auth-page">
      <nav className="auth-nav">
        <Link className="logo" to="/">
          Juris.
        </Link>
        <ThemeToggle />
      </nav>
      <section className="auth-shell">
        <div className="auth-panel">
          <p className="eyebrow">{eyebrow}</p>
          <h1>
            <span className="auth-title-desktop">{title}</span>
            <span className="auth-title-mobile">{mobileTitle}</span>
          </h1>
          {mobileDescription && <p className="auth-mobile-description">{mobileDescription}</p>}
          {children}
          <p className="auth-mobile-trust">{mobileTrust}</p>
        </div>
        <aside className="auth-aside" aria-label="Juris security summary">
          {aside}
        </aside>
      </section>
    </main>
  );
}
