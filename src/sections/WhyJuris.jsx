import { useState } from "react";

const workflowSteps = [
  {
    key: "Upload",
    beforeTitle: "Unstructured PDF",
    beforeText: "Unstructured PDF, scattered clauses, manual review.",
    highlight: "scattered clauses",
    painPoint: "Review starts with searching, copying, and guessing where the important language lives.",
    afterTitle: "Document processed",
    afterText: "Document processed, text extracted, clauses indexed.",
    insight: "Juris turns the file into a searchable legal workspace.",
    risk: "Ready",
    action: "Open the AI workspace and start review.",
  },
  {
    key: "Extract",
    beforeTitle: "Buried clauses",
    beforeText: "Payment, termination, liability clauses buried inside pages.",
    highlight: "buried inside pages",
    painPoint: "Critical terms are mixed into dense paragraphs with no useful structure.",
    afterTitle: "Clauses grouped",
    afterText: "Key clauses grouped by category with source references.",
    insight: "Payment, termination, liability, and dates become scan-ready.",
    risk: "Indexed",
    action: "Jump directly to source-backed clauses.",
  },
  {
    key: "Analyze",
    beforeTitle: "Hidden risk",
    beforeText: "Risks hidden in legal language.",
    highlight: "hidden in legal language",
    painPoint: "Unusual terms can stay invisible until after approval.",
    afterTitle: "Risk surfaced",
    afterText: "High-risk terms surfaced with explanation and confidence.",
    insight: "Juris explains why a term matters before anyone signs.",
    risk: "High risk",
    action: "Review the flagged clause before approval.",
  },
  {
    key: "Ask",
    beforeTitle: "Manual search",
    beforeText: "User manually searches for answers.",
    highlight: "manually searches",
    painPoint: "Every question becomes another hunt through pages of legal text.",
    afterTitle: "Clause-backed answer",
    afterText:
      "Ask: Can this renew automatically? Answer: Yes, clause 6 renews for 12 months unless cancelled.",
    insight: "Plain-English answers stay grounded in the document.",
    risk: "97% confidence",
    action: "Ask follow-up questions without leaving the workspace.",
  },
  {
    key: "Compare",
    beforeTitle: "Version confusion",
    beforeText: "Two versions are hard to compare manually.",
    highlight: "hard to compare",
    painPoint: "Small edits, removed duties, and changed deadlines are easy to miss.",
    afterTitle: "Changes explained",
    afterText: "Added, removed, and changed clauses shown clearly.",
    insight: "Juris summarizes meaningful legal changes, not just text differences.",
    risk: "Changed",
    action: "Review the clauses with the biggest business impact.",
  },
];

export default function WhyJuris() {
  const [activeIndex, setActiveIndex] = useState(0);
  const activeStep = workflowSteps[activeIndex];

  return (
    <section className="section-shell contrast-section why-juris-modern" id="why-juris">
      <div className="section-heading why-juris-heading reveal">
        <p className="eyebrow">WHY JURIS</p>
        <h2>Turn dense legal documents into clear decisions.</h2>
        <p>
          Summaries, clauses, risks, comparisons, and answers — all in one AI legal workspace.
        </p>
      </div>

      <div className="legal-story reveal delay-1">
        <div className="legal-story-steps" aria-label="Legal Chaos to Juris Clarity workflow">
          {workflowSteps.map((step, index) => (
            <button
              className={activeIndex === index ? "active" : ""}
              key={step.key}
              type="button"
              onClick={() => setActiveIndex(index)}
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              {step.key}
            </button>
          ))}
        </div>

        <div className="legal-story-panels" key={activeStep.key}>
          <article className="legal-story-card before-card">
            <div className="story-card-label">
              <div>
                <span>Before Juris</span>
                <b>Legal chaos</b>
              </div>
              <small>Hard to read. Easy to miss.</small>
            </div>
            <div className="dense-doc-preview" aria-label="Dense legal text preview">
              <p>
                The party of the first part shall, notwithstanding any contrary provision herein,
                continue to comply with all operative covenants and{" "}
                <mark>{activeStep.highlight}</mark> subject to renewal, fees, limitations, and
                notice requirements.
              </p>
              <i />
              <i />
              <i />
            </div>
            <div className="story-insight manual">
              <span>{activeStep.beforeTitle}</span>
              <p>{activeStep.beforeText}</p>
              <small>{activeStep.painPoint}</small>
            </div>
          </article>

          <div className="story-arrow" aria-hidden="true">
            <span>→</span>
          </div>

          <article className="legal-story-card after-card">
            <div className="story-card-label">
              <div>
                <span>After Juris</span>
                <b>AI clarity</b>
              </div>
              <small>Clear insights. Zero guesswork.</small>
            </div>
            <div className="ai-output-preview">
              <div>
                <span>Extracted insight</span>
                <strong>{activeStep.afterTitle}</strong>
                <p>{activeStep.afterText}</p>
              </div>
              <div className="risk-badge">{activeStep.risk}</div>
            </div>
            <div className="story-insight clarity">
              <span>Recommended action</span>
              <p>{activeStep.insight}</p>
              <small>{activeStep.action}</small>
            </div>
          </article>
        </div>
      </div>
    </section>
  );
}
