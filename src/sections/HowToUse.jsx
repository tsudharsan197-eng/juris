import Card from "../components/Card.jsx";

const steps = [
  [
    "Create an account",
    "Sign up or sign in securely with Supabase authentication.",
  ],
  [
    "Upload your document",
    "Choose a PDF, DOC, or DOCX file up to 25MB.",
  ],
  [
    "Juris stores it securely",
    "Your file is sent to the backend, verified, and stored privately in Cloudflare R2.",
  ],
  [
    "View your documents",
    "Open the Documents page to view, download, and manage your uploaded files.",
  ],
];

export default function HowToUse() {
  return (
    <section className="section-shell how-use-section" id="how-to-use">
      <div className="section-heading reveal">
        <p className="eyebrow">How to Use</p>
        <h2>How to Use Juris</h2>
        <p>Upload, review, and manage legal documents securely in minutes.</p>
      </div>
      <div className="how-use-grid">
        {steps.map(([title, copy], index) => (
          <Card key={title} className={`how-use-card reveal delay-${index % 3}`}>
            <span className="how-use-number">{String(index + 1).padStart(2, "0")}</span>
            <div>
              <h3>{title}</h3>
              <p>{copy}</p>
            </div>
          </Card>
        ))}
      </div>
    </section>
  );
}
