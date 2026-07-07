import Button from "../components/Button.jsx";

export default function FinalCta() {
  return (
    <section className="final-cta section-shell">
      <div className="reveal">
        <h2>Your legal workspace starts here.</h2>
        <p>
          Create your Juris account and turn every legal document into clear, searchable
          intelligence.
        </p>
        <Button to="/create-account">Create Account</Button>
      </div>
    </section>
  );
}
