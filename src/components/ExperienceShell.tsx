import { useEffect, useRef, type ReactNode } from "react";
import Lenis from "lenis";
import { MotionConfig } from "framer-motion";
import { useLocation } from "react-router-dom";
import CustomCursor from "./CustomCursor";

type ExperienceShellProps = {
  children: ReactNode;
};

export default function ExperienceShell({ children }: ExperienceShellProps) {
  const lenisRef = useRef<Lenis | null>(null);
  const location = useLocation();
  const isDocumentWorkspace = /^\/documents\/[^/]+\/workspace\/?$/.test(location.pathname);
  const isCompassWorkspace = /^\/juris-compass\/?$/.test(location.pathname);
  const isApplicationShell = isDocumentWorkspace || isCompassWorkspace;

  useEffect(() => {
    if (isApplicationShell || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return undefined;

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
  }, [isApplicationShell]);

  useEffect(() => {
    if (!isApplicationShell) return undefined;

    document.documentElement.classList.add("workspace-scroll-locked");
    document.body.classList.add("workspace-scroll-locked");
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });

    return () => {
      document.documentElement.classList.remove("workspace-scroll-locked");
      document.body.classList.remove("workspace-scroll-locked");
    };
  }, [isApplicationShell]);

  useEffect(() => {
    const restoreScroll = (event: Event) => {
      const top = Number((event as CustomEvent).detail);
      if (!Number.isFinite(top)) return;
      lenisRef.current?.scrollTo(top, { immediate: true });
      window.scrollTo({ top, left: 0, behavior: "auto" });
    };

    window.addEventListener("juris:restore-scroll", restoreScroll);
    return () => window.removeEventListener("juris:restore-scroll", restoreScroll);
  }, []);

  return (
    <MotionConfig reducedMotion="user" transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}>
      <div className={`experience-shell${isApplicationShell ? " workspace-route-shell" : ""}${isDocumentWorkspace ? " document-workspace-route-shell" : ""}${isCompassWorkspace ? " compass-route-shell" : ""}`}>
        {children}
        <CustomCursor />
      </div>
    </MotionConfig>
  );
}
