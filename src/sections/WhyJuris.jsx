import { useState } from "react";

const without = [
  ["Hours of manual reading", "Review cycles slow down while teams hunt for meaning line by line."],
  ["Missed clauses", "Critical obligations hide in dense language and scattered sections."],
  ["Hidden legal risks", "Risky renewal, liability, fee, and termination terms are easy to overlook."],
  ["Version confusion", "Redlines and duplicated files make it hard to know what changed."],
  ["Complex legal language", "Teams wait for interpretation before they can make a decision."],
];

const withJuris = [
  ["AI summaries", "Instantly turn long agreements into clear, decision-ready briefs."],
  ["Clause extraction", "Pull out payment terms, dates, obligations, and termination language."],
  ["Risk alerts", "Surface risky or unusual language before a contract is approved."],
  ["Version comparison", "See additions, removals, and modified clauses without manual review."],
  ["Natural-language search", "Ask questions in plain English and get clause-backed answers."],
];

const modes = {
  Summarize: "Get the key points in seconds.",
  Extract: "Find payment terms, termination clauses, and obligations.",
  Detect: "Spot risky language before you sign.",
  Compare: "See what changed between versions.",
  Ask: "Ask questions in plain English.",
};

export default function WhyJuris() {
  const [activeMode, setActiveMode] = useState("Summarize");

  return (
    <section className="section-shell contrast-section why-juris-modern" id="why-juris">
      <div className="section-heading why-juris-heading reveal">
        <p className="eyebrow">WHY JURIS</p>
        <h2>From legal chaos to instant clarity.</h2>
        <p>
          Juris turns dense contracts into summaries, clauses, risks, and answers you can
          actually use.
        </p>
      </div>

      <div className="comparison-tabs reveal delay-1" aria-label="Juris workflow preview modes">
        {Object.keys(modes).map((mode) => (
          <button
            className={activeMode === mode ? "active" : ""}
            key={mode}
            type="button"
            onClick={() => setActiveMode(mode)}
          >
            {mode}
          </button>
        ))}
      </div>

      <div className="comparison-preview reveal delay-1">
        <span>{activeMode}</span>
        <p>{modes[activeMode]}</p>
      </div>

      <div className="before-after modern-comparison">
        <ComparisonCard title="Without Juris" items={without} tone="muted" />
        <div className="comparison-divider" aria-hidden="true">
          <span>→</span>
        </div>
        <ComparisonCard title="With Juris" items={withJuris} tone="accent" />
      </div>
    </section>
  );
}

function ComparisonCard({ title, items, tone }) {
  const [activeItem, setActiveItem] = useState(items[0]);

  return (
    <article className={`comparison-panel comparison-card-modern ${tone} reveal`}>
      <div className="comparison-card-top">
        <span>{tone === "accent" ? "AI workspace" : "Manual workflow"}</span>
        <h3>{title}</h3>
      </div>
      <ul>
        {items.map((item) => (
          <li
            className={activeItem[0] === item[0] ? "active" : ""}
            key={item[0]}
            onMouseEnter={() => setActiveItem(item)}
            onFocus={() => setActiveItem(item)}
            tabIndex={0}
          >
            <span />
            {item[0]}
          </li>
        ))}
      </ul>
      <div className="comparison-detail">
        <strong>{activeItem[0]}</strong>
        <p>{activeItem[1]}</p>
      </div>
    </article>
  );
}
