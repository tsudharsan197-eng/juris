import Button from "../components/Button.jsx";
import { useAuth } from "../components/AuthProvider.jsx";

export default function Hero() {
  const { user, isSignedIn } = useAuth();
  const userName = displayName(user);

  return (
    <section className="hero section-shell">
      <div className="hero-inner">
        <div className="hero-copy reveal">
          {isSignedIn && (
            <div className="hero-greeting" aria-label={`Welcome back, ${userName}`}>
              <span>Welcome back</span>
              <strong>{userName}</strong>
            </div>
          )}
          <p className="eyebrow">AI legal intelligence workspace</p>
          <h1 className="hero-title">
            Legal documents,
            <br />
            decoded by AI.
          </h1>
          <p className="hero-subtext">
            Upload contracts, extract clauses, detect risks, compare versions, and ask legal
            questions in plain English.
          </p>
          <div className="hero-actions">
            <Button to={isSignedIn ? "/upload-document" : "/create-account"}>
              {isSignedIn ? "Upload Documents" : "Create Account"}
            </Button>
            <Button href="#how-it-works" variant="secondary">
              See How It Works
            </Button>
          </div>
        </div>

        <div
          className="hero-preview ai-console reveal delay-1"
          aria-label="Juris AI legal analysis console preview"
        >
          <div className="grain" />
          <div className="console-glow" aria-hidden="true" />
          <div className="console-scan" aria-hidden="true" />

          <div className="console-header">
            <div>
              <span>Document Intelligence</span>
              <strong>Contract scanned</strong>
            </div>
            <div className="console-status">
              <i />
              Live analysis
            </div>
          </div>

          <div className="console-document">
            <div className="doc-chip active">Termination clause detected</div>
            <div className="console-lines">
              <span />
              <span />
              <span />
              <span />
            </div>
            <div className="source-dots" aria-label="Source confidence indicators">
              <i />
              <i />
              <i />
            </div>
          </div>

          <div className="console-grid">
            <section className="console-panel clause-panel">
              <div className="panel-topline">
                <span>Clause Extraction</span>
                <b>12 clauses extracted</b>
              </div>
              <div className="clause-chip-row">
                <span>Payment</span>
                <span>Renewal</span>
                <span>Liability</span>
              </div>
              <div className="clause-rows">
                <p>Governing law identified</p>
                <p>Renewal window captured</p>
                <p>Notice period matched</p>
              </div>
            </section>

            <section className="console-panel risk-signal">
              <span>Risk Signal</span>
              <strong className="risk-score" aria-label="Risk score 82">82</strong>
              <p>Early renewal risk</p>
            </section>
          </div>

          <div className="console-footer-grid">
            <section className="console-panel chat-console">
              <span>Ask Juris</span>
              <div className="console-chat-row user">Can this renew automatically?</div>
              <div className="console-chat-row ai">Yes. Clause 6 renews for 12 months unless cancelled.</div>
            </section>

            <section className="console-panel confidence-panel">
              <span>Confidence</span>
              <strong>97%</strong>
              <div className="confidence-track">
                <i />
              </div>
            </section>
          </div>
        </div>
      </div>
    </section>
  );
}

function displayName(user) {
  const metadata = user?.user_metadata || {};
  const name = metadata.full_name || metadata.name;
  if (name) return firstName(name);
  if (user?.email?.includes("@")) return user.email.split("@")[0];
  return "back";
}

function firstName(name) {
  return String(name).trim().split(/\s+/)[0] || "back";
}
