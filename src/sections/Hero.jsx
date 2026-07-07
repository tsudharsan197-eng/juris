import Button from "../components/Button.jsx";

export default function Hero() {
  return (
    <section className="hero section-shell">
      <div className="hero-inner">
        <div className="hero-copy reveal">
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
            <Button to="/create-account">Create Account</Button>
            <Button href="#how-it-works" variant="secondary">
              See How It Works
            </Button>
          </div>
        </div>

        <div
          className="hero-preview hero-visual reveal delay-1"
          aria-label="Juris product intelligence preview"
        >
          <div className="grain" />
          <div className="visual-tile gradient-tile">
            <span>Document intelligence</span>
            <strong>12 clauses extracted</strong>
          </div>
          <div className="visual-tile doc-preview">
            <div className="doc-line wide" />
            <div className="doc-line" />
            <div className="doc-line short" />
            <div className="annotation">Clause 9: termination</div>
          </div>
          <div className="visual-tile risk-card">
            <span>Risk score</span>
            <strong>82</strong>
            <small>Early termination fee detected</small>
          </div>
          <div className="visual-tile clause-card">
            <span>Clause extraction</span>
            <p>Payment terms, governing law, confidentiality, renewal window.</p>
          </div>
          <div className="visual-tile chat-preview">
            <div className="chat-row user">Can this renew automatically?</div>
            <div className="chat-row ai">Yes. Clause 6 renews for 12 months unless cancelled.</div>
          </div>
          <div className="visual-tile pulse-panel">
            <div />
            <div />
            <div />
          </div>
        </div>
      </div>
    </section>
  );
}
