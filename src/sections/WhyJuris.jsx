import { useState } from "react";
import { motion } from "framer-motion";

const workflowSteps = [
  { key: "Upload", before: "Unstructured PDF. Scattered clauses. Manual review.", highlight: "scattered clauses", after: "Document processed. Text extracted. Clauses indexed.", signal: "READY", note: "A searchable legal workspace in seconds." },
  { key: "Extract", before: "Payment, termination, and liability language buried inside pages.", highlight: "buried inside pages", after: "Key clauses grouped by category with source references.", signal: "12 FOUND", note: "Jump directly to the language that matters." },
  { key: "Analyze", before: "Risk remains hidden inside technical legal language.", highlight: "hidden inside technical legal language", after: "High-impact terms surfaced with explanation and confidence.", signal: "RISK 82", note: "Review the highest-impact language first." },
  { key: "Ask", before: "Every question becomes another manual search through the agreement.", highlight: "manual search", after: "Can this renew automatically? Yes — Clause 6 renews for 12 months.", signal: "97%", note: "Every answer stays attached to its source." },
  { key: "Compare", before: "Small edits and removed duties disappear between document versions.", highlight: "disappear between document versions", after: "Added, removed, and changed clauses shown by legal impact.", signal: "3 CHANGES", note: "Understand change, not just different text." },
];

export default function WhyJuris() {
  const [activeIndex, setActiveIndex] = useState(0);
  const step = workflowSteps[activeIndex];

  return (
    <section className="section-shell transformation-section" id="why-juris">
      <div className="section-folio"><span>02</span><span>TRANSFORMATION</span></div>
      <header className="transformation-heading">
        <p className="accent-note">Before / After</p>
        <h2>Dense language.<br />Clear decisions.</h2>
        <p>Juris does not replace the document. It builds an intelligence layer directly on top of it.</p>
      </header>

      <div className="transformation-layout">
        <nav className="transformation-nav" aria-label="Document transformation steps">
          {workflowSteps.map((item, index) => (
            <button className={index === activeIndex ? "active" : ""} key={item.key} onClick={() => setActiveIndex(index)} type="button">
              <span>{String(index + 1).padStart(2, "0")}</span><b>{item.key}</b><i />
            </button>
          ))}
        </nav>

        <motion.div className="transformation-stage" key={step.key} initial={{ rotateX: -4, y: 30 }} animate={{ rotateX: 0, y: 0 }} transition={{ duration: 0.65 }}>
          <article className="before-document">
            <header><span>BEFORE JURIS</span><b>RAW / UNINDEXED</b></header>
            <div className="legal-copy">
              <small>SECTION 6.2</small>
              <p>The party of the first part shall, notwithstanding any contrary provision herein, continue to comply with all operative covenants and <mark>{step.highlight}</mark> subject to renewal, fees, limitations, and notice requirements.</p>
              <i /><i /><i />
            </div>
            <p>{step.before}</p>
          </article>

          <div className="transformation-axis" aria-hidden="true"><span>→</span><i /></div>

          <article className="after-intelligence">
            <header><span>AFTER JURIS</span><b>{step.signal}</b></header>
            <div className="intelligence-output">
              <small>EXTRACTED INTELLIGENCE</small>
              <h3>{step.key}</h3>
              <p>{step.after}</p>
            </div>
            <footer><span>RECOMMENDED FOCUS</span><p>{step.note}</p></footer>
          </article>
        </motion.div>
      </div>
    </section>
  );
}
