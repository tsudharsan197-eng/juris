import { motion, useInView, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

const stats = [
  [5, "×", "Review velocity", "Less manual reading across every agreement."],
  [24, "/7", "Available", "A document-aware assistant that does not sleep."],
  [100, "%", "Searchable", "Every processed page, clause, and obligation indexed."],
  [82, "/100", "Risk signal", "Prioritized attention instead of undirected review."],
];

function Counter({ target, suffix }) {
  const ref = useRef(null);
  const visible = useInView(ref, { once: true, amount: 0.8 });
  const reduced = useReducedMotion();
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!visible) return undefined;
    if (reduced) { setValue(target); return undefined; }
    const start = performance.now();
    let frame = 0;
    const tick = (now) => {
      const progress = Math.min((now - start) / 1100, 1);
      setValue(Math.round(target * (1 - Math.pow(1 - progress, 3))));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [visible, reduced, target]);
  return <strong ref={ref}>{value}<small>{suffix}</small></strong>;
}

export default function Advantages() {
  return (
    <section className="section-shell evidence-section" id="advantages">
      <div className="section-folio"><span>06</span><span>EVIDENCE</span></div>
      <div className="evidence-heading">
        <p className="accent-note">Designed for attention.</p>
        <h2>More certainty<br />per minute.</h2>
      </div>
      <div className="evidence-strip">
        {stats.map(([value, suffix, label, copy], index) => (
          <motion.article key={label} whileHover={{ y: -8 }} transition={{ type: "spring", stiffness: 280, damping: 25 }}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <Counter target={value} suffix={suffix} />
            <h3>{label}</h3>
            <p>{copy}</p>
          </motion.article>
        ))}
      </div>
    </section>
  );
}
