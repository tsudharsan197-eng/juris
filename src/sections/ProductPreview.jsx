export default function ProductPreview() {
  return (
    <section className="section-shell product-section">
      <div className="section-heading reveal">
        <p className="eyebrow">Product preview</p>
        <h2>One workspace for legal intelligence.</h2>
      </div>
      <div className="product-grid">
        <article className="product-card upload-card reveal">
          <span>Document Upload</span>
          <h3>Master Service Agreement.pdf</h3>
          <div className="upload-bar"><span /></div>
          <p>Encrypted upload complete. 38 pages indexed.</p>
        </article>
        <article className="product-card summary-card reveal delay-1">
          <span>AI Summary</span>
          <p>
            This agreement defines service levels, payment milestones, renewal terms, data
            handling obligations, and termination rights.
          </p>
        </article>
        <article className="product-card score-card reveal delay-2">
          <span>Risk Score</span>
          <strong>82</strong>
          <p>High attention: indemnity, renewal, early termination fee.</p>
        </article>
        <article className="product-card clauses-card reveal">
          <span>Clause Extraction</span>
          <div>Confidentiality</div>
          <div>Termination</div>
          <div>Governing Law</div>
          <div>Payment Terms</div>
        </article>
        <article className="product-card compare-card reveal delay-1">
          <span>Contract Comparison</span>
          <div className="diff add">+ 30 day written notice</div>
          <div className="diff remove">- automatic 24 month renewal</div>
          <div className="diff edit">~ liability capped at fees paid</div>
        </article>
        <article className="product-card chat-card reveal delay-2">
          <span>AI Chat</span>
          <div className="chat-row user">Can this agreement be terminated early?</div>
          <div className="chat-row ai">
            Yes. Clause 9 allows termination with 30 days written notice. However, Clause 11
            includes an early termination fee.
          </div>
        </article>
        <article className="product-card analytics-card reveal">
          <span>Analytics Dashboard</span>
          <div className="bars">
            <i style={{ height: "44%" }} />
            <i style={{ height: "72%" }} />
            <i style={{ height: "54%" }} />
            <i style={{ height: "88%" }} />
            <i style={{ height: "64%" }} />
          </div>
        </article>
      </div>
    </section>
  );
}
