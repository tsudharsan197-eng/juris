import { Link } from "react-router-dom";

export default function Footer() {
  return (
    <footer className="footer">
      <div>
        <Link to="/" className="footer-logo">
          Juris.
        </Link>
        <p>AI legal intelligence for contracts, clauses, risks, and answers.</p>
      </div>
      <div className="footer-links">
        <a href="#what-is-juris">What is Juris</a>
        <a href="#how-it-works">How it Works</a>
        <a href="#advantages">Advantages</a>
      </div>
      <div className="footer-links">
        <Link to="/sign-in">Sign In</Link>
        <Link to="/create-account">Create Account</Link>
        <Link to="/forgot-password">Forgot Password</Link>
      </div>
      <p className="copyright">Copyright {new Date().getFullYear()} Juris. All rights reserved.</p>
    </footer>
  );
}
