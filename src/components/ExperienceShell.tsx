import { useEffect, useRef, type ReactNode } from "react";
import Lenis from "lenis";
import { MotionConfig } from "framer-motion";
import CustomCursor from "./CustomCursor";

type ExperienceShellProps = {
  children: ReactNode;
};

export default function ExperienceShell({ children }: ExperienceShellProps) {
  const lenisRef = useRef<Lenis | null>(null);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return undefined;

    const lenis = new Lenis({
      duration: 1.15,
      lerp: 0.085,
      smoothWheel: true,
      syncTouch: false,
      anchors: { offset: -96 },
    });
    let frame = 0;

    const update = (time: number) => {
      lenis.raf(time);
      frame = window.requestAnimationFrame(update);
    };

    lenisRef.current = lenis;
    lenis.on("scroll", () => window.dispatchEvent(new Event("juris:lenis-scroll")));
    frame = window.requestAnimationFrame(update);

    return () => {
      window.cancelAnimationFrame(frame);
      lenis.destroy();
      lenisRef.current = null;
    };
  }, []);

  return (
    <MotionConfig reducedMotion="user" transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}>
      <div className="experience-shell">
        {children}
        <CustomCursor />
      </div>
    </MotionConfig>
  );
}
