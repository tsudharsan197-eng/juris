import { useEffect, useState } from "react";

const transformationSteps = ["Source", "Extract", "Interpret", "Act"];

export default function WhyJuris() {
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    const handleScrollStep = (event) => {
      const next = Number(event.detail);
      if (Number.isInteger(next) && next >= 0 && next < transformationSteps.length) {
        setActiveIndex(next);
      }
    };

    window.addEventListener("juris:transformation-step", handleScrollStep);
    return () => window.removeEventListener("juris:transformation-step", handleScrollStep);
  }, []);

  return (
    <section className="section-shell transformation-section" id="why-juris">
      <div className="transformation-pin">
        <div className="transformation-meta">
          <span>Before / After</span>
          <span>Legal transformation / 02</span>
          <i className="transformation-entry-rule" aria-hidden="true" />
        </div>

        <header className="transformation-heading">
          <h2><span>Raw language.</span><span>Clear action.</span></h2>
          <p>Juris preserves the source document while turning dense language into structured, verifiable intelligence.</p>
        </header>

        <ol className="transformation-progress" aria-label="Legal transformation progress">
          {transformationSteps.map((step, index) => (
            <li className={index === activeIndex ? "active" : ""} key={step} aria-current={index === activeIndex ? "step" : undefined}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <b>{step}</b>
              <i aria-hidden="true" />
            </li>
          ))}
        </ol>

        <div className="transformation-stage">
          <article className="transformation-raw">
            <header>
              <span>Raw clause</span>
              <b>Raw / Unindexed</b>
            </header>
            <div className="transformation-raw-copy">
              <div className="transformation-clause-id">
                <span>Section 6.2</span>
                <strong>Term and renewal</strong>
              </div>
              <blockquote>
                “The Agreement shall <mark>renew automatically</mark> for successive <mark>twelve-month periods</mark> unless either party provides <mark>thirty days written notice</mark> before the renewal date.”
              </blockquote>
            </div>
            <footer>
              <span>Src 06.2</span>
              <span>Page 06 / 38</span>
              <span>Raw / Unindexed</span>
            </footer>
          </article>

          <div className="transformation-bridge">
            <div className="transformation-connectors" aria-hidden="true"><i /><i /><i /></div>
            <aside className="transformation-rail" aria-label="Clause extraction index">
              <header><span>Extraction</span><b>Live</b></header>
              <dl>
                <div><dt>Clause</dt><dd>06.2</dd></div>
                <div><dt>Type</dt><dd>Term / Renewal</dd></div>
                <div><dt>Confidence</dt><dd><i className="transformation-confidence">97</i>%</dd></div>
                <div><dt>Risk</dt><dd className="risk-value">Medium</dd></div>
                <div><dt>Source</dt><dd className="source-value">Attached</dd></div>
              </dl>
              <footer>Clause indexed</footer>
            </aside>
          </div>

          <article className="transformation-decision">
            <header>
              <span>Decision</span>
              <b>Verified</b>
            </header>
            <div className="transformation-decision-content">
              <small>Decision-ready insight</small>
              <h3>Auto-renewal detected</h3>
              <p>The agreement renews for another 12 months unless written notice is provided at least 30 days before renewal.</p>
              <section className="transformation-recommendation">
                <span>Recommended action</span>
                <p>Review the renewal date and schedule a notice reminder.</p>
              </section>
            </div>
            <footer>
              <span>Source 06.2</span>
              <span>Confidence 97%</span>
              <span>Status / Verified</span>
            </footer>
          </article>
        </div>

        <i className="transformation-exit-rule" aria-hidden="true" />
      </div>
    </section>
  );
}
