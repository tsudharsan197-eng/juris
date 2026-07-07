const without = [
  "Hours spent reading",
  "Missed clauses",
  "Hidden legal risks",
  "Version confusion",
  "Complex legal language",
];

const withJuris = [
  "AI summaries",
  "Clause extraction",
  "Risk alerts",
  "Version comparison",
  "Natural-language search",
];

export default function WhyJuris() {
  return (
    <section className="section-shell contrast-section" id="why-juris">
      <div className="section-heading reveal">
        <p className="eyebrow">Why Juris</p>
        <h2>Stop reading contracts. Start understanding them.</h2>
      </div>
      <div className="before-after">
        <Panel title="Without Juris" items={without} tone="muted" />
        <Panel title="With Juris" items={withJuris} tone="accent" />
      </div>
    </section>
  );
}

function Panel({ title, items, tone }) {
  return (
    <article className={`comparison-panel ${tone} reveal`}>
      <h3>{title}</h3>
      <ul>
        {items.map((item) => (
          <li key={item}>
            <span />
            {item}
          </li>
        ))}
      </ul>
    </article>
  );
}
