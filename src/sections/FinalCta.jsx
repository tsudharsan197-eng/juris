import { motion } from "framer-motion";
import Button from "../components/Button.jsx";

export default function FinalCta() {
  return (
    <section className="final-cta section-shell">
      <div className="section-folio"><span>08</span><span>BEGIN</span></div>
      <motion.div className="final-cta-layout" initial={{ clipPath: "inset(0 0 100% 0)" }} whileInView={{ clipPath: "inset(0 0 0% 0)" }} viewport={{ once: true, amount: 0.35 }} transition={{ duration: 1.1 }}>
        <span className="final-cta-index">THE DOCUMENT IS ONLY THE BEGINNING.</span>
        <h2>Make every word<br /><em>work harder.</em></h2>
        <div><p>Turn every legal document into clear, searchable intelligence.</p><Button to="/create-account">Create Account</Button></div>
      </motion.div>
    </section>
  );
}
