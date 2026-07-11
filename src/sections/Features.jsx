import { Bot, ChartNoAxesCombined, FileDiff, Radar, Search, ShieldAlert } from "lucide-react";
import MotionReveal from "../components/MotionReveal";

const features = [
  ["AI-first document intelligence", "Summaries, entities, obligations, and legal context are extracted in one clean workspace.", Radar],
  ["Risk detection before signing", "Flag unusual terms, fee exposure, renewal traps, and liability language before approval.", ShieldAlert],
  ["Contract version comparison", "Track additions, removals, and modified clauses without spreadsheet-style chaos.", FileDiff],
  ["Semantic search across documents", "Search by meaning across contracts, policies, agreements, and legal PDFs.", Search],
  ["AI legal assistant", "Ask plain-English questions and receive grounded answers tied to document clauses.", Bot],
  ["Legal analytics dashboard", "Monitor review velocity, risk categories, agreement types, and document health.", ChartNoAxesCombined],
];

export default function Features() {
  return (
    <section className="section-shell feature-section" id="why-different">
      <div className="section-folio"><span>03</span><span>CAPABILITIES</span></div>
      <MotionReveal className="section-heading feature-heading">
        <p className="accent-note">The intelligence layer.</p>
        <h2>Every clause.<br /><em>Made legible.</em></h2>
        <p>One intelligence system for understanding what a document says, what changed, and what deserves attention.</p>
      </MotionReveal>
      <div className="feature-list">
        {features.map(([title, copy, Icon], index) => (
          <article
            className="feature-row"
            key={title}
          >
            <span className="feature-row-number">0{index + 1}</span>
            <div className="feature-symbol"><Icon size={21} strokeWidth={1.5} /></div>
            <div><h3>{title}</h3><p>{copy}</p></div>
            <i aria-hidden="true">↗</i>
          </article>
        ))}
      </div>
    </section>
  );
}
