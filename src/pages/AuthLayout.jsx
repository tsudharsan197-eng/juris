import { Link } from "react-router-dom";
import ThemeToggle from "../components/ThemeToggle.jsx";

export default function AuthLayout({ eyebrow, title, children, aside }) {
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
          <h1>{title}</h1>
          {children}
        </div>
        <aside className="auth-aside" aria-label="Juris security summary">
          {aside}
        </aside>
      </section>
    </main>
  );
}
