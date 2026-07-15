import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";

export default function Footer() {
  return (
    <footer className="footer">
      <div className="footer-brand">
        <Link to="/" className="footer-logo">Juris.</Link>
        <p>AI legal intelligence for contracts, clauses, risks, and answers.</p>
        <span>Built for clarity.</span>
      </div>
      <div className="footer-nav-group">
        <div className="footer-links"><span>Explore</span><Link to="/juris-compass">Juris Compass <ArrowUpRight size={13} /></Link><a href="#what-is-juris">Intelligence <ArrowUpRight size={13} /></a><a href="#how-it-works">Workflow <ArrowUpRight size={13} /></a><a href="#advantages">Advantages <ArrowUpRight size={13} /></a></div>
        <div className="footer-links"><span>Account</span><Link to="/sign-in">Sign In</Link><Link to="/create-account">Create Account</Link><Link to="/forgot-password">Reset access</Link></div>
      </div>
      <div className="copyright"><span>© {new Date().getFullYear()} Juris. All rights reserved.</span><span>AI legal intelligence / v1.0</span></div>
    </footer>
  );
}
