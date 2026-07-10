import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import MotionReveal from "../components/MotionReveal";

const steps = [
  ["Upload", "Securely upload contracts, agreements, policies, or legal PDFs."],
  ["Extract", "Juris extracts text, metadata, parties, dates, headings, and clauses."],
  ["Analyze", "AI summarizes the document, identifies obligations, and detects risky language."],
  ["Ask", "Users can ask questions about the document in plain English."],
  ["Compare", "Compare contract versions and highlight changes, additions, removals, and modified clauses."],
  ["Report", "Generate dashboards, legal insights, and exportable reports."],
];

export default function Workflow() {
  const [activeStep, setActiveStep] = useState(0);

  return (
    <section className="section-shell workflow-section" id="how-it-works">
      <div className="section-folio"><span>05</span><span>PROCESS</span></div>
      <MotionReveal className="section-heading workflow-heading">
        <p className="accent-note">How Juris works.</p>
        <h2>From document<br />to decision.</h2>
        <p>Juris turns complex legal documents into actionable intelligence through a simple AI workflow.</p>
      </MotionReveal>
      <div className="timeline">
        {steps.map(([title, copy], index) => (
          <motion.button
            className={`timeline-step ${activeStep === index ? "active" : ""}`}
            key={title}
            type="button"
            onClick={() => setActiveStep(index)}
            whileHover={{ y: -6 }}
            layout
          >
            <span className="step-number">{String(index + 1).padStart(2, "0")}</span>
            <h3>{title}</h3>
            <AnimatePresence initial={false}>
              {activeStep === index && (
                <motion.p initial={{ clipPath: "inset(0 0 100% 0)", height: 0 }} animate={{ clipPath: "inset(0 0 0% 0)", height: "auto" }} exit={{ clipPath: "inset(0 0 100% 0)", height: 0 }}>
                  {copy}
                </motion.p>
              )}
            </AnimatePresence>
            <span className="timeline-state">{activeStep === index ? "Active" : "Explore"}</span>
          </motion.button>
        ))}
      </div>
      <div className="timeline-progress" aria-hidden="true"><motion.i animate={{ width: `${((activeStep + 1) / steps.length) * 100}%` }} /></div>
    </section>
  );
}
