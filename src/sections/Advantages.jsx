const stats = [
  ["5x", "faster review"],
  ["24/7", "AI assistant"],
  ["100%", "searchable documents"],
  ["Risk-first", "analysis"],
];

export default function Advantages() {
  return (
    <section className="section-shell advantages-section" id="advantages">
      <div className="section-heading reveal">
        <p className="eyebrow">Advantages</p>
        <h2>Built to save time, reduce risk, and improve clarity.</h2>
      </div>
      <div className="stat-grid">
        {stats.map(([value, label]) => (
          <article className="stat-card reveal" key={label}>
            <strong>{value}</strong>
            <span>{label}</span>
          </article>
        ))}
      </div>
    </section>
  );
}
