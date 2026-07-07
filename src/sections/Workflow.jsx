const steps = [
  ["Upload", "Securely upload contracts, agreements, policies, or legal PDFs."],
  ["Extract", "Juris extracts text, metadata, parties, dates, headings, and clauses."],
  ["Analyze", "AI summarizes the document, identifies obligations, and detects risky language."],
  ["Ask", "Users can ask questions about the document in plain English."],
  ["Compare", "Compare contract versions and highlight changes, additions, removals, and modified clauses."],
  ["Report", "Generate dashboards, legal insights, and exportable reports."],
];

export default function Workflow() {
  return (
    <section className="section-shell workflow-section" id="how-it-works">
      <div className="section-heading reveal">
        <p className="eyebrow">How Juris works</p>
        <h2>From document to decision.</h2>
        <p>
          Juris turns complex legal documents into actionable intelligence through a simple AI
          workflow.
        </p>
      </div>
      <div className="timeline">
        {steps.map(([title, copy], index) => (
          <article className={`timeline-step reveal delay-${index % 3}`} key={title}>
            <span className="step-number">{String(index + 1).padStart(2, "0")}</span>
            <h3>{title}</h3>
            <p>{copy}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
