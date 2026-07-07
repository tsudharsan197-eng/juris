import Card from "../components/Card.jsx";

const features = [
  ["AI-first document intelligence", "Summaries, entities, obligations, and legal context are extracted in one clean workspace.", "◆"],
  ["Risk detection before signing", "Flag unusual terms, fee exposure, renewal traps, and liability language before approval.", "△"],
  ["Contract version comparison", "Track additions, removals, and modified clauses without spreadsheet-style chaos.", "↕"],
  ["Semantic search across documents", "Search by meaning across contracts, policies, agreements, and legal PDFs.", "⌁"],
  ["AI legal assistant", "Ask plain-English questions and receive grounded answers tied to document clauses.", "✦"],
  ["Legal analytics dashboard", "Monitor review velocity, risk categories, agreement types, and document health.", "▣"],
];

export default function Features() {
  return (
    <section className="section-shell" id="why-different">
      <div className="section-heading reveal">
        <p className="eyebrow">Why Juris is better</p>
        <h2>Why Juris is different.</h2>
      </div>
      <div className="feature-grid">
        {features.map(([title, copy, symbol], index) => (
          <Card key={title} className={`feature-card reveal delay-${index % 3}`}>
            <div className="feature-symbol">{symbol}</div>
            <h3>{title}</h3>
            <p>{copy}</p>
          </Card>
        ))}
      </div>
    </section>
  );
}
