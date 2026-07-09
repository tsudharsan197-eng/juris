import { useState } from "react";

const clauseRows = [
  {
    label: "Confidentiality",
    detail: "Mutual confidentiality obligations found with source references attached.",
  },
  {
    label: "Termination",
    detail: "30 day written notice required before early termination.",
  },
  {
    label: "Governing Law",
    detail: "Governing law detected and linked to the dispute resolution section.",
  },
  {
    label: "Payment Terms",
    detail: "Milestone payments and late-fee language extracted for review.",
  },
];

export default function ProductPreview() {
  const [selectedClause, setSelectedClause] = useState(clauseRows[1]);

  return (
    <section className="section-shell product-section">
      <div className="section-heading product-heading reveal">
        <p className="eyebrow">Product preview</p>
        <h2>One workspace for legal intelligence.</h2>
      </div>
      <div className="product-grid">
        <article className="product-card upload-card reveal">
          <div className="product-card-top">
            <span>Document Upload</span>
            <em>Processed</em>
          </div>
          <h3>Master Service Agreement.pdf</h3>
          <div className="upload-bar" aria-label="Upload progress">
            <span />
          </div>
          <p>Scanning clauses...</p>
          <small>38 pages indexed</small>
        </article>

        <article className="product-card summary-card reveal delay-1">
          <div className="product-card-top">
            <span>AI Summary</span>
            <em>Sources attached</em>
          </div>
          <p>
            This agreement defines service levels, payment milestones, renewal terms, data
            handling obligations, and termination rights.
          </p>
          <small>Confidence 97%</small>
        </article>

        <article className="product-card score-card reveal delay-2">
          <div className="product-card-top">
            <span>Risk Score</span>
            <em className="danger">High risk</em>
          </div>
          <strong aria-label="Risk score 82">82</strong>
          <p>Indemnity, renewal, and early termination fee require attention.</p>
        </article>

        <article className="product-card clauses-card reveal">
          <div className="product-card-top">
            <span>Clause Extraction</span>
            <em>4 clauses found</em>
          </div>
          <div className="clause-row-list">
            {clauseRows.map((clause) => (
              <button
                className={selectedClause.label === clause.label ? "selected" : ""}
                key={clause.label}
                type="button"
                onClick={() => setSelectedClause(clause)}
              >
                {clause.label}
              </button>
            ))}
          </div>
          <div className="clause-detail-preview">
            <span>{selectedClause.label}</span>
            <p>{selectedClause.detail}</p>
          </div>
        </article>

        <article className="product-card compare-card reveal delay-1">
          <div className="product-card-top">
            <span>Contract Comparison</span>
            <em>3 changes</em>
          </div>
          <div className="diff add">+ 30 day written notice</div>
          <div className="diff remove">- automatic 24 month renewal</div>
          <div className="diff edit">~ liability capped at fees paid</div>
        </article>

        <article className="product-card chat-card reveal delay-2">
          <div className="product-card-top">
            <span>AI Chat</span>
            <em>Live answer</em>
          </div>
          <div className="chat-row user">Can this agreement be terminated early?</div>
          <div className="chat-row ai">
            Yes. Clause 9 allows termination with 30 days written notice. Clause 11 includes an
            early termination fee.
          </div>
        </article>

        <article className="product-card analytics-card reveal">
          <div className="product-card-top">
            <span>Analytics Dashboard</span>
            <em>Live</em>
          </div>
          <div className="bars" aria-label="Legal analytics chart">
            <i style={{ "--bar-height": "44%" }} />
            <i style={{ "--bar-height": "72%" }} />
            <i style={{ "--bar-height": "54%" }} />
            <i style={{ "--bar-height": "88%" }} />
            <i style={{ "--bar-height": "64%" }} />
          </div>
        </article>
      </div>
    </section>
  );
}
