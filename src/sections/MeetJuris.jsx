import { motion, useReducedMotion } from "framer-motion";
import MotionReveal from "../components/MotionReveal";
import useMediaQuery from "../hooks/useMediaQuery";

const capabilities = [
  ["Understand", "Structured summaries reveal the document's purpose, parties, obligations, and dates."],
  ["Search", "Find clauses and answers by meaning, not exact wording."],
  ["Compare", "See legal and commercial changes between versions without manual redlining."],
  ["Protect", "Surface risky language and missing protections before approval."],
];

export default function MeetJuris() {
  const isMobile = useMediaQuery("(max-width: 1023px)");
  const reduceMotion = useReducedMotion();

  return (
    <section className="section-shell editorial-intro" id="what-is-juris">
      <div className="section-folio"><span>01</span><span>WHAT IS JURIS</span></div>
      <MotionReveal className="editorial-statement">
        <p className="accent-note">A new reading system for legal work.</p>
        <h2>Read less.<br />Know more.</h2>
        <p>Juris transforms contracts and legal documents into searchable, structured intelligence. Nothing is abstracted away from its source.</p>
      </MotionReveal>

      <div className="capability-ledger">
        {capabilities.map(([title, copy], index) => (
          <motion.article
            className="capability-line"
            custom={index}
            key={title}
            initial={reduceMotion ? false : isMobile ? { clipPath: "inset(0 0 100% 0)", x: index % 2 ? 42 : -42, y: 54, scale: .96 } : { clipPath: "inset(0 100% 0 0)" }}
            whileInView={reduceMotion ? { opacity: 1 } : isMobile ? { clipPath: "inset(0 0 0% 0)", x: 0, y: 0, scale: 1 } : { clipPath: "inset(0 0% 0 0)" }}
            viewport={isMobile ? { once: false, amount: .24 } : { once: true, amount: .55 }}
            transition={reduceMotion ? { duration: .16 } : isMobile ? { duration: .7, delay: index * .035, ease: [.2, .78, .2, 1] } : { duration: .9, delay: index * .07 }}
          >
            <span>{String(index + 1).padStart(2, "0")}</span>
            <h3>{title}</h3>
            <p>{copy}</p>
            <i aria-hidden="true">↗</i>
          </motion.article>
        ))}
      </div>
    </section>
  );
}
