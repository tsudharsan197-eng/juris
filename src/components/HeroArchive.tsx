import useMediaQuery from "../hooks/useMediaQuery";

const archiveLayerCount = 120;

export default function HeroArchive() {
  const isMobile = useMediaQuery("(max-width: 1023px)");
  const renderedLayerCount = isMobile ? 36 : archiveLayerCount;

  return (
    <div className="hero-machine">
      <div className="hero-machine-registration" aria-hidden="true">
        <span>ARCHIVE / 001</span>
        <span>RAW DOCUMENT</span>
        <span>120 LAYERS</span>
      </div>

      <div className="hero-monolith">
        <div className="hero-archive-layers">
          {Array.from({ length: renderedLayerCount }, (_, index) => (
            <i
              className="hero-archive-layer"
              data-layer={index}
              key={index}
              style={{
                top: `${(index / renderedLayerCount) * 100}%`,
                height: `calc(${100 / renderedLayerCount}% + 0.55px)`,
              }}
            />
          ))}
        </div>
        <div className="hero-monolith-cover">
          <header className="hero-archive-cover-head">
            <span>COMPRESSED LEGAL ARCHIVE</span>
            <span>JURIS / FILE 001</span>
          </header>

          <div className="hero-archive-cover-meta">
            <span>38 PAGES</span>
            <span><b className="hero-layer-count">120</b> LAYERS</span>
            <span>REV / 06</span>
          </div>

          <div className="hero-archive-cover-title">
            <small>MASTER SERVICE AGREEMENT</small>
            <strong>DOCUMENT<br />BEFORE<br /><em>INTELLIGENCE</em></strong>
          </div>

          <dl className="hero-archive-data">
            <div><dt>TYPE</dt><dd>AGREEMENT</dd></div>
            <div><dt>STATUS</dt><dd>RAW</dd></div>
            <div><dt>VERSION</dt><dd>06</dd></div>
            <div><dt>SOURCE</dt><dd>USER UPLOAD</dd></div>
            <div><dt>INDEX</dt><dd>PENDING</dd></div>
          </dl>

          <div className="hero-archive-clauses">
            <span>TERM AND TERMINATION</span>
            <span>GOVERNING LAW</span>
            <span>PAYMENT OBLIGATIONS</span>
            <span>RENEWAL WINDOW</span>
            <span>LIABILITY LIMITATION</span>
          </div>

          <div className="hero-archive-registration-line" />
          <div className="hero-archive-scan" />

          <footer className="hero-archive-cover-foot">
            <span>RAW DOCUMENT / INDEX PENDING</span>
            <b>J / 001</b>
          </footer>

          <ol className="hero-archive-index" aria-hidden="true">
            <li>001</li><li>002</li><li>003</li><li>004</li><li>005</li>
          </ol>
        </div>
      </div>

      <div className="hero-constructed-interface">
        <aside className="hero-machine-panel hero-machine-index">
          <div className="hero-interface-content">
            <span>FILE INDEX</span>
            <ol>
              <li><i>01</i><b>Document</b></li>
              <li><i>02</i><b>Clauses</b></li>
              <li><i>03</i><b>Risk</b></li>
              <li><i>04</i><b>Answer</b></li>
            </ol>
            <small>MSA-2026-041<br />REVISION 05</small>
          </div>
        </aside>

        <div className="hero-machine-panel hero-machine-document">
          <div className="hero-interface-content">
            <header><span>PAGE 06 / 38</span><b>MASTER SERVICES AGREEMENT</b></header>
            <article>
              <span>6.2</span>
              <h3>TERM AND RENEWAL</h3>
              <p>This Agreement renews automatically for successive twelve-month periods unless either party provides thirty days written notice.</p>
              <mark>Automatic renewal / 12 months</mark>
              <footer><span>SOURCE 06.2</span><b>06</b></footer>
            </article>
          </div>
        </div>

        <aside className="hero-machine-panel hero-machine-intelligence">
          <div className="hero-interface-content">
            <header><span>INTELLIGENCE</span><b>EXTRACTED</b></header>
            <section className="hero-machine-confidence"><span>CONFIDENCE</span><strong>97%</strong><i /></section>
            <section className="hero-machine-signal"><span>RISK SIGNAL</span><b>HIGH</b><p>Automatic renewal</p><small>SOURCE 06.2</small></section>
            <section className="hero-machine-citation"><span>GROUNDED ANSWER</span><p>Renews for 12 months unless cancelled with 30 days notice.</p></section>
          </div>
        </aside>

        <div className="hero-machine-scanner"><span>EXTRACTING / 06.2</span></div>
      </div>

      <div className="hero-machine-ruler" aria-hidden="true">
        {Array.from({ length: 9 }, (_, index) => <i key={index}>{String(index + 1).padStart(2, "0")}</i>)}
      </div>
    </div>
  );
}
