import { motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";
import useMediaQuery from "../hooks/useMediaQuery";

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
  const isMobile = useMediaQuery("(max-width: 1023px)");
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      className={className}
      initial={reduceMotion ? false : isMobile
        ? { clipPath: "inset(0 0 100% 0)", y: 58, scale: .985 }
        : { clipPath: "inset(0 0 100% 0)", y: 36, rotateX: -3 }}
      whileInView={reduceMotion ? { opacity: 1 } : isMobile
        ? { clipPath: "inset(0 0 0% 0)", y: 0, scale: 1 }
        : { clipPath: "inset(0 0 0% 0)", y: 0, rotateX: 0 }}
      viewport={isMobile ? { once: false, amount: Math.min(amount, .18) } : { once: true, amount }}
      transition={reduceMotion ? { duration: .16 } : isMobile
        ? { delay, duration: .72, ease: [0.25, .8, .25, 1] }
        : { delay, duration: 1.05, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
