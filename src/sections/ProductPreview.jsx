import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Bot, FileDiff, FileText, ScanSearch, ShieldAlert } from "lucide-react";

const modes = [
  { id: "document", label: "Document", Icon: FileText, status: "38 pages indexed", title: "Master Service Agreement" },
  { id: "clauses", label: "Clauses", Icon: ScanSearch, status: "12 clauses extracted", title: "Termination & renewal" },
  { id: "risk", label: "Risk", Icon: ShieldAlert, status: "3 signals require review", title: "Risk priority 82" },
  { id: "ask", label: "Ask", Icon: Bot, status: "97% confidence", title: "Source-backed answer" },
  { id: "compare", label: "Compare", Icon: FileDiff, status: "3 material changes", title: "Version 04 → 05" },
];

const clauseRows = ["Confidentiality", "Termination", "Governing Law", "Payment Terms"];

export default function ProductPreview() {
  const [activeMode, setActiveMode] = useState(modes[1]);
  const [selectedClause, setSelectedClause] = useState("Termination");

  return (
    <section className="section-shell product-section" id="product-workspace">
      <div className="section-folio"><span>07</span><span>PRODUCT SYSTEM</span></div>
      <header className="product-editorial-heading">
        <p className="accent-note">The workspace.</p>
        <h2>Legal work,<br />reconstructed.</h2>
        <p>A working interface for reading, questioning, and comparing legal documents with precision.</p>
      </header>

      <div className="software-frame">
        <header className="software-bar">
          <div><span>JURIS</span><i>DOCUMENT / 001</i></div>
          <strong>Master Service Agreement.pdf</strong>
          <small>PROCESSED · 14:32:08</small>
        </header>

        <aside className="software-nav" aria-label="Product demo modes">
          <span>TOOLS</span>
          {modes.map((mode, index) => (
            <button className={activeMode.id === mode.id ? "active" : ""} key={mode.id} onClick={() => setActiveMode(mode)} type="button">
              <i>{String(index + 1).padStart(2, "0")}</i><mode.Icon size={16} strokeWidth={1.5} /><b>{mode.label}</b>
            </button>
          ))}
          <div className="software-user"><i>TS</i><span>Tharun<br /><small>OWNER</small></span></div>
        </aside>

        <main className="software-document">
          <div className="document-toolbar"><span>PAGE 06 / 38</span><span>112%</span></div>
          <article className="document-sheet">
            <header><span>6.</span><h3>TERM AND TERMINATION</h3></header>
            <p>This Agreement shall commence on the Effective Date and shall continue for an initial period of twelve months unless terminated earlier in accordance with this section.</p>
            <p className="document-highlight">Either party may terminate this Agreement upon thirty (30) days prior written notice. The Agreement will renew automatically for successive twelve-month periods.</p>
            <p>Termination shall not affect rights, remedies, obligations or liabilities accrued before the termination date.</p>
            <div className="source-marker">SOURCE 06.2</div>
          </article>
        </main>

        <aside className="software-inspector">
          <AnimatePresence mode="wait">
            <motion.div key={activeMode.id} initial={{ clipPath: "inset(0 0 100% 0)", y: 22 }} animate={{ clipPath: "inset(0 0 0% 0)", y: 0 }} exit={{ clipPath: "inset(0 0 100% 0)" }}>
              <span className="inspector-label">{activeMode.label.toUpperCase()} INTELLIGENCE</span>
              <h3>{activeMode.title}</h3>
              <p>{activeMode.status}</p>
            </motion.div>
          </AnimatePresence>

          <div className="inspector-meter"><span>CONFIDENCE</span><strong>97%</strong><i><b /></i></div>

          <div className="inspector-clauses">
            <span>CLAUSE INDEX</span>
            {clauseRows.map((clause, index) => (
              <button className={selectedClause === clause ? "active" : ""} key={clause} onClick={() => setSelectedClause(clause)} type="button">
                <i>{String(index + 1).padStart(2, "0")}</i><span>{clause}</span><b>{index === 1 ? "HIGH" : "FOUND"}</b>
              </button>
            ))}
          </div>

          <div className="inspector-answer">
            <span>ASK JURIS</span>
            <p>Can this renew automatically?</p>
            <strong>Yes. Clause 6 renews for twelve months unless cancelled with 30 days written notice.</strong>
            <small>SOURCE 06.2 ATTACHED</small>
          </div>
        </aside>
      </div>
    </section>
  );
}
