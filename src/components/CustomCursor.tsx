import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";
import useMediaQuery from "../hooks/useMediaQuery";

const INTERACTIVE_SELECTOR = "a, button, input, textarea, select, summary, [role='button']";

export default function CustomCursor() {
  const reducedMotion = useReducedMotion();
  const finePointer = useMediaQuery("(hover: hover) and (pointer: fine)");
  const [visible, setVisible] = useState(false);
  const [interactive, setInteractive] = useState(false);
  const [position, setPosition] = useState({ x: -100, y: -100 });

  useEffect(() => {
    if (!finePointer || reducedMotion) return undefined;

    const onMove = (event: PointerEvent) => {
      setPosition({ x: event.clientX, y: event.clientY });
      setVisible(true);
    };
    const onLeave = () => setVisible(false);
    const onOver = (event: PointerEvent) => {
      setInteractive(Boolean((event.target as Element | null)?.closest?.(INTERACTIVE_SELECTOR)));
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    document.addEventListener("pointerover", onOver, { passive: true });
    document.documentElement.addEventListener("mouseleave", onLeave);

    return () => {
      window.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerover", onOver);
      document.documentElement.removeEventListener("mouseleave", onLeave);
    };
  }, [finePointer, reducedMotion]);

  if (reducedMotion || !finePointer) return null;

  return (
    <>
      <motion.div
        className="cursor-dot"
        animate={{ x: position.x - 3, y: position.y - 3, opacity: visible ? 1 : 0 }}
        transition={{ type: "spring", stiffness: 900, damping: 52, mass: 0.08 }}
      />
      <motion.div
        className="cursor-ring"
        animate={{
          x: position.x - (interactive ? 24 : 16),
          y: position.y - (interactive ? 24 : 16),
          width: interactive ? 48 : 32,
          height: interactive ? 48 : 32,
          opacity: visible ? 1 : 0,
          backgroundColor: "rgba(0,0,0,0)",
        }}
        transition={{ type: "spring", stiffness: 420, damping: 34, mass: 0.2 }}
      />
    </>
  );
}
