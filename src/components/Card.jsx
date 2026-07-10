import { motion } from "framer-motion";

export default function Card({ children, className = "" }) {
  return (
    <motion.article
      className={`card ${className}`.trim()}
      whileHover={{ y: -8, rotateX: 1.2, rotateY: -1.2 }}
      transition={{ type: "spring", stiffness: 260, damping: 24 }}
    >
      {children}
    </motion.article>
  );
}
