import { useEffect, useState } from "react";

const fileIndex = [
  { number: "001", label: "Intake", meta: "File registered" },
  { number: "002", label: "Parties", meta: "Entities identified" },
  { number: "003", label: "Clauses", meta: "Terms indexed" },
  { number: "004", label: "Risk", meta: "Signals isolated" },
  { number: "005", label: "Answer", meta: "Sources grounded" },
];

const documentFragments = [
  {
    number: "1.1",
    title: "Parties",
    body: "This Master Services Agreement is entered into by Northstar Systems, Inc. (Client) and Meridian Advisory LLC (Provider).",
    source: "SRC 01.1",
  },
  {
    number: "4.2",
    title: "Payment terms",
    body: "Undisputed invoices are payable within thirty (30) days of receipt. Late balances may accrue interest at 1.0% per month.",
    source: "SRC 04.2",
  },
  {
    number: "6.2",
    title: "Term and renewal",
    body: "The Agreement renews automatically for successive twelve-month periods unless either party provides thirty (30) days written notice.",
    source: "SRC 06.2",
  },
  {
    number: "8.4",
    title: "Liability",
    body: "Provider liability is limited to fees paid during the preceding six months, except for confidentiality and indemnification obligations.",
    source: "SRC 08.4",
  },
  {
    number: "12.1",
    title: "Governing law",
    body: "This Agreement is governed by the laws of the State of New York, without regard to conflict-of-law principles.",
    source: "SRC 12.1",
  },
];

const clauseIndex = [
  ["01", "Confidentiality", "FOUND"],
  ["02", "Payment", "FOUND"],
  ["03", "Auto-renewal", "REVIEW"],
  ["04", "Liability", "REVIEW"],
];

export default function ProductPreview() {
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    const handleCaseFileStep = (event) => {
      const nextIndex = Number(event.detail);
      if (Number.isInteger(nextIndex) && nextIndex >= 0 && nextIndex < fileIndex.length) {
        setActiveIndex(nextIndex);
      }
    };

    window.addEventListener("juris:casefile-step", handleCaseFileStep);
    return () => window.removeEventListener("juris:casefile-step", handleCaseFileStep);
  }, []);

  return (
    <section className="product-section casefile-section" id="product-workspace">
      <div className="casefile-stage">
        <div className="casefile-cover" aria-hidden="true">
          <span className="casefile-cover-classification">CONFIDENTIAL / CONTROLLED COPY</span>
          <div className="casefile-cover-title">
            <small>JURIS / CASE FILE 006</small>
            <strong>Document<br />becomes<br /><em>intelligence.</em></strong>
          </div>
          <dl className="casefile-cover-register">
            <div><dt>FILE</dt><dd>MSA-2026-041</dd></div>
            <div><dt>REVISION</dt><dd>05 / FINAL</dd></div>
            <div><dt>ACCESS</dt><dd>OWNER ONLY</dd></div>
          </dl>
          <i className="casefile-fold casefile-fold-left" />
          <i className="casefile-fold casefile-fold-right" />
          <i className="casefile-registration casefile-registration-a" />
          <i className="casefile-registration casefile-registration-b" />
        </div>

        <div className="casefile-workspace">
          <header className="casefile-system-bar">
            <div><strong>JURIS</strong><span>LEGAL INTELLIGENCE SYSTEM</span></div>
            <span>CASE / MSA-2026-041</span>
            <b className="casefile-process-status">REVIEW / READY</b>
          </header>

          <nav className="casefile-tabs" aria-label="Confidential case file index">
            <span className="casefile-index-label">FILE INDEX</span>
            <div className="casefile-tab-list">
              {fileIndex.map((item, index) => (
                <button
                  aria-pressed={activeIndex === index}
                  className={activeIndex === index ? "active" : ""}
                  key={item.number}
                  onClick={() => setActiveIndex(index)}
                  type="button"
                >
                  <i>{item.number}</i>
                  <span>{item.label}</span>
                  <small>{item.meta}</small>
                </button>
              ))}
            </div>
            <div className="casefile-index-record">
              <span>38 PAGES</span>
              <span>REV 05</span>
              <b>PRIVATE</b>
            </div>
          </nav>

          <main className="casefile-reader">
            <header className="casefile-reader-bar">
              <span>DOCUMENT / ORIGINAL</span>
              <span>PAGE 06 OF 38</span>
              <span>OCR / ENGLISH</span>
            </header>
            <div className="casefile-paper-bed">
              <div className="casefile-ruler" aria-hidden="true">
                {Array.from({ length: 12 }, (_, index) => <i key={index}>{String(index + 1).padStart(2, "0")}</i>)}
              </div>
              <div className="casefile-processing-stage" aria-hidden="true">
                <header className="casefile-processing-head">
                  <span>JURIS / STRUCTURE ENGINE</span>
                  <b>LIVE PROCESS</b>
                  <small>MSA-2026-041</small>
                </header>

                <div className="casefile-process-fragment process-fragment-clause">
                  <small>CLAUSE / 06.2</small>
                  <strong>TERM AND RENEWAL</strong>
                  <span>AUTO RENEW / 30 DAY NOTICE</span>
                  <i>SOURCE 06.2</i>
                </div>

                <div className="casefile-process-fragment process-fragment-entity-a">
                  <small>ENTITY EXTRACTED / 01</small>
                  <strong>NORTHSTAR SYSTEMS</strong>
                  <span>ROLE / CLIENT</span>
                </div>

                <div className="casefile-process-fragment process-fragment-entity-b">
                  <small>ENTITY EXTRACTED / 02</small>
                  <strong>MERIDIAN ADVISORY LLC</strong>
                  <span>ROLE / PROVIDER</span>
                </div>

                <div className="casefile-process-fragment process-fragment-payment">
                  <small>SECTION 04.2</small>
                  <strong>PAYMENT TERMS</strong>
                  <span>NET 30 / INTEREST 1.0%</span>
                  <i>SOURCE 04.2</i>
                </div>

                <div className="casefile-process-fragment process-fragment-risk">
                  <small>RISK SIGNAL / HIGH</small>
                  <strong>AUTO RENEWAL DETECTED</strong>
                  <span>REVIEW BEFORE SIGNING</span>
                </div>

                <div className="casefile-process-fragment process-fragment-liability">
                  <small>SECTION 08.4</small>
                  <strong>LIABILITY LIMITATION</strong>
                  <span>EXCEPTION / INDEMNIFICATION</span>
                </div>

                <div className="casefile-process-fragment process-fragment-confidence">
                  <small>ANALYSIS CONFIDENCE</small>
                  <strong><i className="casefile-process-confidence-value">97</i>%</strong>
                  <span>5 / 5 SOURCES GROUNDED</span>
                </div>

                <div className="casefile-process-fragment process-fragment-snippet">
                  <small>OCR BOUND / 17</small>
                  <p>“renews automatically for successive twelve-month periods unless either party provides thirty days written notice”</p>
                </div>

                <div className="casefile-process-keywords">
                  <span>CONFIDENTIALITY</span>
                  <span>GOVERNING LAW</span>
                  <span>OBLIGATION</span>
                  <span>CITATION READY</span>
                </div>

                <div className="casefile-process-lock process-lock-a"><span>OCR / LOCKED</span></div>
                <div className="casefile-process-lock process-lock-b"><span>ENTITY / LINKED</span></div>
                <div className="casefile-process-lock process-lock-c"><span>CLAUSE / INDEXED</span></div>

                <i className="casefile-process-connector connector-a" />
                <i className="casefile-process-connector connector-b" />
                <i className="casefile-process-connector connector-c" />
                <i className="casefile-process-connector connector-d" />

                <footer className="casefile-processing-foot">
                  <span>UPLOAD</span><i /><span>PARSE</span><i /><span>UNDERSTAND</span><i /><span>STRUCTURE</span><i /><span>DELIVER</span>
                </footer>
              </div>
              <article className="casefile-document" aria-label="Master Services Agreement document preview">
                <i className="casefile-page-mark casefile-page-mark-a" />
                <i className="casefile-page-mark casefile-page-mark-b" />
                <div className="casefile-document-content">
                  <header className="casefile-document-header">
                    <span>CONFIDENTIAL</span>
                    <small>REVISION 05 / 14 JUNE 2026</small>
                    <h3>MASTER SERVICES<br />AGREEMENT</h3>
                    <dl>
                      <div><dt>CLIENT</dt><dd>Northstar Systems, Inc.</dd></div>
                      <div><dt>PROVIDER</dt><dd>Meridian Advisory LLC</dd></div>
                    </dl>
                  </header>
                  <div className="casefile-document-body">
                    {documentFragments.map((fragment, index) => (
                      <section className={activeIndex === index ? "active" : ""} key={fragment.number}>
                        <div><b>{fragment.number}</b><h4>{fragment.title}</h4><span>{fragment.source}</span></div>
                        <p>{fragment.body}</p>
                      </section>
                    ))}
                  </div>
                  <footer className="casefile-document-footer"><span>MSA-2026-041 / CONTROLLED COPY</span><b>06</b></footer>
                </div>
                <div className="casefile-scan-line" aria-hidden="true"><span>OCR / READING</span></div>
              </article>
            </div>
          </main>

          <aside className="casefile-intelligence" aria-label="Live document intelligence">
            <header>
              <span>INTELLIGENCE MARGIN</span>
              <b>LIVE EXTRACTION</b>
            </header>

            <section className="casefile-intel-block casefile-confidence">
              <div><span>ANALYSIS CONFIDENCE</span><small>DOCUMENT WIDE</small></div>
              <strong className="casefile-confidence-number">97</strong>
              <i><b /></i>
            </section>

            <section className="casefile-intel-block casefile-entities">
              <span>IDENTIFIED PARTIES</span>
              <div><b>01</b><p>Northstar Systems, Inc.<small>CLIENT</small></p></div>
              <div><b>02</b><p>Meridian Advisory LLC<small>PROVIDER</small></p></div>
            </section>

            <section className="casefile-intel-block casefile-clauses">
              <div className="casefile-intel-title"><span>CLAUSE INDEX</span><b><i className="casefile-clause-count">12</i> FOUND</b></div>
              {clauseIndex.map(([number, label, status], index) => (
                <div className={`casefile-clause-row ${activeIndex === Math.min(index + 1, 4) ? "active" : ""}`} key={label}>
                  <i>{number}</i><span>{label}</span><b>{status}</b>
                </div>
              ))}
            </section>

            <section className="casefile-intel-block casefile-risk">
              <div className="casefile-intel-title"><span>RISK SIGNAL</span><b><i className="casefile-risk-number">3</i> ITEMS</b></div>
              <p><b>HIGH</b><span>Automatic renewal</span><small>SOURCE 06.2</small></p>
              <p><b>MED</b><span>Liability exception</span><small>SOURCE 08.4</small></p>
            </section>

            <section className="casefile-intel-block casefile-answer">
              <span>GROUNDED ANSWER / SOURCE ATTACHED</span>
              <p>Can this agreement renew automatically?</p>
              <strong>Yes. Clause 6.2 renews the agreement for twelve months unless either party gives 30 days written notice.</strong>
              <small>CONFIDENCE 97% / SOURCE 06.2</small>
            </section>
          </aside>
        </div>

        <div className="casefile-exit-sheet" aria-hidden="true">
          <span>JURIS / REVIEW COMPLETE</span>
          <strong>DOCUMENT<br />UNDERSTOOD.</strong>
          <small>38 PAGES / 12 CLAUSES / 3 RISK SIGNALS</small>
          <i className="casefile-registration casefile-registration-a" />
          <i className="casefile-registration casefile-registration-b" />
        </div>
      </div>
    </section>
  );
}
