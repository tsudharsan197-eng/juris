import Card from "../components/Card.jsx";

const keywords = [
  ["Understand", "Turn dense documents into structured summaries."],
  ["Search", "Find obligations, dates, parties, and clauses instantly."],
  ["Compare", "See additions, removals, and wording shifts clearly."],
  ["Protect", "Surface risky terms before they become expensive."],
];

export default function MeetJuris() {
  return (
    <section className="section-shell split-section" id="what-is-juris">
      <div className="section-copy reveal">
        <p className="eyebrow">What is Juris</p>
        <h2>Meet Juris.</h2>
        <p>
          Juris is an AI-powered legal intelligence workspace that transforms lengthy contracts
          and legal documents into clear summaries, searchable clauses, risk insights, version
          comparisons, and AI-powered answers.
        </p>
      </div>
      <div className="keyword-grid">
        {keywords.map(([title, copy], index) => (
          <Card key={title} className={`keyword-card reveal delay-${index % 3}`}>
            <span>0{index + 1}</span>
            <h3>{title}</h3>
            <p>{copy}</p>
          </Card>
        ))}
      </div>
    </section>
  );
}
