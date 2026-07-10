import { motion } from "framer-motion";
import MotionReveal from "../components/MotionReveal";

const steps = [
  ["Create an account", "Sign up or sign in securely with Supabase authentication."],
  ["Upload your document", "Choose a PDF, DOC, or DOCX file up to 25MB."],
  ["Juris stores it securely", "Your file is verified by the backend and stored privately in Cloudflare R2."],
  ["Open your workspace", "View, download, manage, and analyze every processed document."],
];

export default function HowToUse() {
  return (
    <section className="section-shell use-sequence" id="how-to-use">
      <div className="section-folio"><span>04</span><span>GETTING STARTED</span></div>
      <MotionReveal className="sequence-heading">
        <p className="accent-note">Four deliberate steps.</p>
        <h2>Secure in.<br />Intelligence out.</h2>
      </MotionReveal>
      <div className="sequence-list">
        {steps.map(([title, copy], index) => (
          <motion.article
            className="sequence-step"
            key={title}
            initial={{ x: index % 2 ? 80 : -80, rotateY: index % 2 ? -4 : 4 }}
            whileInView={{ x: 0, rotateY: 0 }}
            viewport={{ once: true, amount: 0.5 }}
            transition={{ duration: 0.9 }}
          >
            <strong>{String(index + 1).padStart(2, "0")}</strong>
            <div><h3>{title}</h3><p>{copy}</p></div>
            <span>{index === steps.length - 1 ? "READY" : "NEXT"}</span>
          </motion.article>
        ))}
      </div>
    </section>
  );
}
