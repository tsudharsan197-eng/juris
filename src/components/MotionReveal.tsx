import { motion } from "framer-motion";
import type { ReactNode } from "react";

type MotionRevealProps = {
  children: ReactNode;
  className?: string;
  delay?: number;
  amount?: number;
};

export default function MotionReveal({
  children,
  className = "",
  delay = 0,
  amount = 0.2,
}: MotionRevealProps) {
  return (
    <motion.div
      className={className}
      initial={{ clipPath: "inset(0 0 100% 0)", y: 36, rotateX: -3 }}
      whileInView={{ clipPath: "inset(0 0 0% 0)", y: 0, rotateX: 0 }}
      viewport={{ once: true, amount }}
      transition={{ delay, duration: 1.05, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
