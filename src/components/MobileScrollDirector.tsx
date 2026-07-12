import { useLayoutEffect } from "react";
import { gsap } from "gsap";
import { CustomEase } from "gsap/CustomEase";
import { ScrollTrigger } from "gsap/ScrollTrigger";

const mobileScenes = [
  { selector: ".editorial-intro", number: "01", label: "UNDERSTANDING", title: ["READ LESS.", "KNOW MORE."], tone: "blue", pattern: "rise" },
  { selector: ".transformation-section", number: "02", label: "TRANSFORMATION", title: ["RAW LANGUAGE.", "CLEAR ACTION."], tone: "rust", pattern: "split" },
  { selector: ".feature-section", number: "03", label: "CAPABILITIES", title: ["EVERY CLAUSE.", "MADE LEGIBLE."], tone: "blue", pattern: "track" },
  { selector: ".workflow-section", number: "04", label: "PROCESS", title: ["DOCUMENT.", "DECISION."], tone: "rust", pattern: "stack" },
  { selector: ".evidence-section", number: "05", label: "EVIDENCE", title: ["MORE CERTAINTY.", "PER MINUTE."], tone: "lime", pattern: "index" },
  { selector: ".casefile-section", number: "06", label: "PRODUCT SYSTEM", title: ["DOCUMENT.", "INTELLIGENCE."], tone: "blue", pattern: "window" },
  { selector: ".footer", number: "07", label: "JURIS / CONTINUE", title: ["BUILT FOR", "CLARITY."], tone: "rust", pattern: "takeover" },
];

export default function MobileScrollDirector() {
  useLayoutEffect(() => {
    gsap.registerPlugin(ScrollTrigger, CustomEase);

    const media = gsap.matchMedia();
    media.add(
      {
        mobile: "(max-width: 1023px)",
        reduce: "(prefers-reduced-motion: reduce)",
      },
      (matchContext) => {
        const { mobile, reduce } = matchContext.conditions as { mobile: boolean; reduce: boolean };
        if (!mobile || reduce) return undefined;

        document.documentElement.classList.add("mobile-scroll-directed");
        const mechanicalEase = CustomEase.create("jurisMobileMechanical", "M0,0 C0.58,0 0.22,1 1,1");
        const scrollUpdate = () => ScrollTrigger.update();
        window.addEventListener("juris:lenis-scroll", scrollUpdate);

        const animationContext = gsap.context(() => {
          const heroScene = document.querySelector<HTMLElement>(".hero-scene");
          const heroLockup = document.querySelector<HTMLElement>(".hero-lockup");
          const heroBottom = document.querySelector<HTMLElement>(".hero-bottom-grid");
          const heroMonolith = document.querySelector<HTMLElement>(".hero-monolith");
          const heroInterface = document.querySelector<HTMLElement>(".hero-constructed-interface");
          const heroScanner = document.querySelector<HTMLElement>(".hero-machine-scanner");
          const heroRule = gsap.utils.toArray<HTMLElement>(".hero-rule > span");
          const heroTitleLines = gsap.utils.toArray<HTMLElement>(".hero-title-back > span");
          const heroForegroundLines = gsap.utils.toArray<HTMLElement>(".hero-title-foreground > span");
          const heroActions = gsap.utils.toArray<HTMLElement>(".hero-actions .btn");
          const archiveDetails = gsap.utils.toArray<HTMLElement>(
            ".hero-archive-cover-head, .hero-archive-cover-meta, .hero-archive-cover-foot",
          );

          gsap.timeline({ defaults: { ease: mechanicalEase } })
            .fromTo(heroRule, { y: -18, clipPath: "inset(100% 0 0 0)" }, { y: 0, clipPath: "inset(0% 0 0 0)", duration: .38, stagger: .045 }, .02)
            .fromTo(heroScene, { xPercent: 18, scale: .94, clipPath: "inset(0 0 100% 0)" }, { xPercent: 0, scale: 1, clipPath: "inset(0 0 0% 0)", duration: .82 }, .14)
            .fromTo(archiveDetails, { x: 22, clipPath: "inset(0 100% 0 0)" }, { x: 0, clipPath: "inset(0 0% 0 0)", duration: .48, stagger: .06 }, .38)
            .fromTo(heroActions, { y: 24, clipPath: "inset(0 0 100% 0)" }, { y: 0, clipPath: "inset(0 0 0% 0)", duration: .42, stagger: .07 }, .64);

          if (heroLockup && heroScene && heroBottom) {
            const heroExit = gsap.timeline({
              scrollTrigger: {
                trigger: ".hero",
                start: "top top",
                end: "bottom 28%",
                scrub: .55,
                invalidateOnRefresh: true,
              },
            })
              .to(heroLockup, { yPercent: -20, scale: .94, transformOrigin: "left top", ease: "none", duration: 1 }, 0)
              .to(heroScene, { yPercent: -19, scale: .88, rotateY: -7, transformOrigin: "right center", transformPerspective: 900, ease: "none", duration: 1 }, 0)
              .to(heroBottom, { yPercent: -14, ease: "none", duration: .72 }, .22)
              .to([heroTitleLines[0], heroForegroundLines[0]], { xPercent: -9, ease: "none", duration: .48 }, .34)
              .to([heroTitleLines[1], heroForegroundLines[1]], { xPercent: 7, ease: "none", duration: .48 }, .38)
              .to([heroTitleLines[2], heroForegroundLines[2]], { xPercent: -5, ease: "none", duration: .48 }, .42);

            if (heroMonolith && heroInterface && heroScanner) {
              heroExit
                .to(heroMonolith, { scaleX: .045, xPercent: -92, transformOrigin: "left center", duration: .36, ease: mechanicalEase }, .43)
                .fromTo(heroInterface, { clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0% 0 0)", duration: .4, ease: mechanicalEase }, .48)
                .fromTo(heroScanner, { scaleY: 0, x: 0 }, { scaleY: 1, x: 0, transformOrigin: "top center", duration: .16, ease: mechanicalEase }, .62)
                .to(heroScanner, { x: () => Math.max(0, heroInterface.offsetWidth - 2), duration: .3, ease: "none" }, .68);
            }
          }

          mobileScenes.forEach((scene, index) => {
            const section = document.querySelector<HTMLElement>(scene.selector);
            const panel = document.querySelector<HTMLElement>(`.mobile-transition-panel[data-scene="${index}"]`);
            if (!section || !panel) return;

            const folio = section.querySelector<HTMLElement>(".section-folio");
            const transitionTitle = panel.querySelector<HTMLElement>(".mobile-transition-title");
            const transitionTitleTrack = panel.querySelector<HTMLElement>(".mobile-transition-title-track");
            const transitionIndex = panel.querySelector<HTMLElement>(".mobile-transition-index");
            const transitionAccent = panel.querySelector<HTMLElement>(".mobile-transition-velocity-rule");
            const titleVelocity = transitionTitleTrack
              ? gsap.quickTo(transitionTitleTrack, "x", { duration: .2, ease: "power3.out" })
              : undefined;
            const accentVelocity = transitionAccent
              ? gsap.quickTo(transitionAccent, "scaleX", { duration: .18, ease: "power2.out" })
              : undefined;
            const transition = gsap.timeline({
              scrollTrigger: {
                trigger: section,
                start: "top 102%",
                end: "top 22%",
                scrub: .66,
                invalidateOnRefresh: true,
                onUpdate: (self) => {
                  const velocity = gsap.utils.clamp(-1, 1, self.getVelocity() / 2200);
                  titleVelocity?.(velocity * 26);
                  accentVelocity?.(1 + Math.abs(velocity) * .55);
                },
              },
            });

            if (scene.pattern === "split") {
              transition.fromTo(panel, { xPercent: -102 }, { xPercent: 102, duration: 1, ease: "none" }, 0);
            } else if (scene.pattern === "track") {
              transition.fromTo(panel, { xPercent: 102 }, { xPercent: -102, duration: 1, ease: "none" }, 0);
            } else if (scene.pattern === "index") {
              transition
                .fromTo(panel, { clipPath: "inset(100% 0 0 0)" }, { clipPath: "inset(0% 0 0 0)", duration: .48, ease: mechanicalEase }, 0)
                .to(panel, { clipPath: "inset(0 0 100% 0)", duration: .52, ease: mechanicalEase }, .48);
            } else if (scene.pattern === "window") {
              transition
                .fromTo(panel, { scaleX: 0, transformOrigin: "left center" }, { scaleX: 1, duration: .46, ease: mechanicalEase }, 0)
                .to(panel, { scaleX: 0, transformOrigin: "right center", duration: .54, ease: mechanicalEase }, .46);
            } else if (scene.pattern === "takeover") {
              transition
                .fromTo(panel, { yPercent: 102 }, { yPercent: 0, duration: .55, ease: mechanicalEase }, 0)
                .to(panel, { yPercent: -102, duration: .45, ease: mechanicalEase }, .55);
            } else {
              transition.fromTo(panel, { yPercent: 102 }, { yPercent: -102, duration: 1, ease: "none" }, 0);
            }

            const sectionEntry = scene.pattern === "split"
              ? { x: -34, y: 54, scale: .965, clipPath: "inset(0 12% 0 0)" }
              : scene.pattern === "track"
                ? { x: 38, y: 42, scale: .96, clipPath: "inset(0 0 0 12%)" }
                : scene.pattern === "stack"
                  ? { y: 118, scale: .91, rotateX: 5, clipPath: "inset(12% 0 0 0)" }
                  : scene.pattern === "index"
                    ? { x: -28, y: 76, scale: .95, clipPath: "inset(8% 0 0 0)" }
                    : scene.pattern === "window"
                      ? { y: 34, scale: .88, clipPath: "inset(10% 7% 10% 7%)" }
                      : { y: 88, scale: .95, clipPath: "inset(10% 0 0 0)" };

            transition
              .fromTo(transitionTitle, { clipPath: "inset(0 0 100% 0)", yPercent: 38 }, { clipPath: "inset(0 0 0% 0)", yPercent: 0, duration: .34, ease: mechanicalEase }, .1)
              .fromTo(transitionIndex, { scale: .72, opacity: .12 }, { scale: 1.18, opacity: .72, transformOrigin: "left bottom", duration: .54, ease: "none" }, .08)
              .fromTo(section, sectionEntry, { x: 0, y: 0, scale: 1, rotateX: 0, clipPath: "inset(0% 0 0 0)", duration: .68, ease: mechanicalEase }, .3);

            if (folio) {
              transition.fromTo(folio, { x: -34, opacity: .18 }, { x: 0, opacity: 1, duration: .34, ease: mechanicalEase }, .5);
            }
          });

          const transformationSection = document.querySelector<HTMLElement>(".transformation-section");
          const transformationRaw = document.querySelector<HTMLElement>(".transformation-raw");
          const transformationBridge = document.querySelector<HTMLElement>(".transformation-bridge");
          const transformationRail = document.querySelector<HTMLElement>(".transformation-rail");
          const transformationDecision = document.querySelector<HTMLElement>(".transformation-decision");
          const transformationMarks = gsap.utils.toArray<HTMLElement>(".transformation-raw mark");

          if (transformationSection && transformationRaw && transformationRail && transformationDecision) {
            let activeIndex = -1;
            gsap.timeline({
              scrollTrigger: {
                trigger: transformationSection,
                start: "top 76%",
                end: "bottom 24%",
                scrub: .62,
                invalidateOnRefresh: true,
                onUpdate: ({ progress }) => {
                  const next = Math.min(3, Math.floor(progress * 4));
                  if (next === activeIndex) return;
                  activeIndex = next;
                  window.dispatchEvent(new CustomEvent("juris:transformation-step", { detail: next }));
                },
              },
            })
              .fromTo(transformationRaw, { xPercent: -14, clipPath: "inset(0 12% 0 0)" }, { xPercent: 0, clipPath: "inset(0 0% 0 0)", duration: .34, ease: mechanicalEase }, 0)
              .fromTo(transformationMarks, { "--mobile-highlight-progress": 0 }, { "--mobile-highlight-progress": 1, duration: .28, stagger: .05, ease: "none" }, .2)
              .fromTo(transformationBridge, { "--mobile-bridge-progress": 0 }, { "--mobile-bridge-progress": 1, duration: .34, ease: "none" }, .34)
              .fromTo(transformationRail, { scaleY: .18, clipPath: "inset(0 0 82% 0)" }, { scaleY: 1, clipPath: "inset(0 0 0% 0)", transformOrigin: "top center", duration: .3, ease: mechanicalEase }, .4)
              .fromTo(transformationDecision, { xPercent: 14, clipPath: "inset(0 0 0 14%)" }, { xPercent: 0, clipPath: "inset(0 0 0 0%)", duration: .34, ease: mechanicalEase }, .64)
              .to(transformationRaw, { xPercent: -6, scale: .985, transformOrigin: "left center", duration: .24, ease: "none" }, .76);
          }

          gsap.utils.toArray<HTMLElement>(".feature-row").forEach((row, index) => {
            gsap.fromTo(row, { xPercent: index % 2 ? 12 : -12, y: 68, scale: .95, clipPath: "inset(0 0 100% 0)", "--mobile-row-progress": 0 }, {
              xPercent: 0,
              y: 0,
              scale: 1,
              clipPath: "inset(0 0 0% 0)",
              "--mobile-row-progress": 1,
              ease: "none",
              scrollTrigger: {
                trigger: row,
                start: "top 96%",
                end: "top 52%",
                scrub: .48,
                invalidateOnRefresh: true,
                onEnter: () => row.classList.add("is-mobile-active"),
                onLeave: () => row.classList.remove("is-mobile-active"),
                onEnterBack: () => row.classList.add("is-mobile-active"),
                onLeaveBack: () => row.classList.remove("is-mobile-active"),
              },
            });
          });

          gsap.fromTo(".feature-heading", { xPercent: -8 }, {
            xPercent: 5,
            ease: "none",
            scrollTrigger: { trigger: ".feature-section", start: "top 72%", end: "bottom 28%", scrub: .7, invalidateOnRefresh: true },
          });

          gsap.fromTo(".workflow-section", { "--mobile-process-progress": 0 }, {
            "--mobile-process-progress": 1,
            ease: "none",
            scrollTrigger: { trigger: ".workflow-section", start: "top 80%", end: "bottom 20%", scrub: .4, invalidateOnRefresh: true },
          });

          gsap.utils.toArray<HTMLElement>(".timeline-step").forEach((step, index) => {
            gsap.fromTo(step, { y: 58, scale: .94, rotateX: 3, clipPath: "inset(0 0 76% 0)", opacity: .5 }, {
              y: 0,
              scale: 1,
              rotateX: 0,
              clipPath: "inset(0 0 0% 0)",
              opacity: 1,
              ease: "none",
              scrollTrigger: {
                trigger: step,
                start: "top 104%",
                end: "top 54%",
                scrub: .5,
                invalidateOnRefresh: true,
              },
            });

            ScrollTrigger.create({
              trigger: step,
              start: "top 62%",
              end: "bottom 38%",
              invalidateOnRefresh: true,
              onEnter: () => {
                step.classList.add("is-mobile-active");
                window.dispatchEvent(new CustomEvent("juris:workflow-step", { detail: index }));
              },
              onLeave: () => step.classList.remove("is-mobile-active"),
              onEnterBack: () => {
                step.classList.add("is-mobile-active");
                window.dispatchEvent(new CustomEvent("juris:workflow-step", { detail: index }));
              },
              onLeaveBack: () => step.classList.remove("is-mobile-active"),
            });
          });

          gsap.utils.toArray<HTMLElement>(".evidence-strip article").forEach((card, index) => {
            const metric = card.querySelector<HTMLElement>("strong");
            const cardTimeline = gsap.timeline({
              scrollTrigger: { trigger: card, start: "top 104%", end: "top 48%", scrub: .52, invalidateOnRefresh: true },
            });
            cardTimeline.fromTo(card, { xPercent: index % 2 ? 11 : -11, y: 52, clipPath: "inset(0 0 82% 0)" }, {
              xPercent: 0,
              y: 0,
              clipPath: "inset(0 0 0% 0)",
              ease: "none",
            });
            if (metric) {
              cardTimeline.fromTo(metric, { scale: .55, xPercent: index % 2 ? 20 : -20 }, { scale: 1, xPercent: 0, transformOrigin: "left bottom", ease: mechanicalEase }, .22);
            }
          });

          const caseWorkspace = document.querySelector<HTMLElement>(".casefile-workspace");
          const processingStage = document.querySelector<HTMLElement>(".casefile-processing-stage");
          const documentPage = document.querySelector<HTMLElement>(".casefile-document");
          const scanLine = document.querySelector<HTMLElement>(".casefile-scan-line");

          if (caseWorkspace && processingStage && documentPage && scanLine) {
            let caseIndex = -1;
            gsap.timeline({
              scrollTrigger: {
                trigger: caseWorkspace,
                start: "top 94%",
                end: "top 16%",
                scrub: .62,
                invalidateOnRefresh: true,
                onUpdate: ({ progress }) => {
                  const next = Math.min(4, Math.floor(progress * 5));
                  if (next === caseIndex) return;
                  caseIndex = next;
                  window.dispatchEvent(new CustomEvent("juris:casefile-step", { detail: next }));
                },
              },
            })
              .fromTo(caseWorkspace, { y: 72, clipPath: "inset(0 0 100% 0)" }, { y: 0, clipPath: "inset(0 0 0% 0)", duration: .36, ease: mechanicalEase }, 0)
              .fromTo(processingStage, { clipPath: "inset(48% 0 48% 0)" }, { clipPath: "inset(0% 0 0% 0)", duration: .26, ease: mechanicalEase }, .24)
              .fromTo(scanLine, { y: 0, scaleX: 0 }, { y: () => Math.max(0, documentPage.offsetHeight - 70), scaleX: 1, transformOrigin: "left center", duration: .48, ease: "none" }, .36)
              .to(processingStage, { clipPath: "inset(0 0 100% 0)", duration: .28, ease: mechanicalEase }, .68)
              .fromTo(documentPage, { clipPath: "inset(0 0 14% 0)" }, { clipPath: "inset(0 0 0% 0)", duration: .24, ease: mechanicalEase }, .72);
          }

          gsap.fromTo(".footer-logo", { xPercent: -24, scale: .88, clipPath: "inset(0 100% 0 0)" }, {
            xPercent: 0,
            scale: 1,
            clipPath: "inset(0 0% 0 0)",
            ease: "none",
            scrollTrigger: { trigger: ".footer", start: "top 96%", end: "top 46%", scrub: .55, invalidateOnRefresh: true },
          });
        });

        let alive = true;
        let refreshFrame = 0;
        let lastWidth = window.innerWidth;
        let lastHeight = window.innerHeight;
        const requestRefresh = () => {
          window.cancelAnimationFrame(refreshFrame);
          refreshFrame = window.requestAnimationFrame(() => ScrollTrigger.refresh());
        };
        const handleViewportResize = () => {
          const widthChanged = Math.abs(window.innerWidth - lastWidth) > 2;
          const substantialHeightChange = Math.abs(window.innerHeight - lastHeight) > 120;
          if (!widthChanged && !substantialHeightChange) return;
          lastWidth = window.innerWidth;
          lastHeight = window.innerHeight;
          requestRefresh();
        };

        document.fonts.ready.then(() => { if (alive) requestRefresh(); });
        window.addEventListener("orientationchange", requestRefresh);
        window.visualViewport?.addEventListener("resize", handleViewportResize);

        return () => {
          alive = false;
          window.cancelAnimationFrame(refreshFrame);
          window.removeEventListener("orientationchange", requestRefresh);
          window.removeEventListener("juris:lenis-scroll", scrollUpdate);
          window.visualViewport?.removeEventListener("resize", handleViewportResize);
          animationContext.revert();
          document.documentElement.classList.remove("mobile-scroll-directed");
        };
      },
    );

    return () => media.revert();
  }, []);

  return (
    <div className="mobile-transition-layer" aria-hidden="true">
      {mobileScenes.map((scene, index) => (
        <div
          className={`mobile-transition-panel tone-${scene.tone} pattern-${scene.pattern}`}
          data-scene={index}
          data-pattern={scene.pattern}
          key={scene.selector}
        >
          <span className="mobile-transition-kicker">JURIS / {scene.label}</span>
          <b className="mobile-transition-index">{scene.number}</b>
          <strong className="mobile-transition-title">
            <span className="mobile-transition-title-track"><i>{scene.title[0]}</i><i>{scene.title[1]}</i></span>
          </strong>
          <span className="mobile-transition-coordinate">{scene.number} / 07&nbsp;&nbsp; MOBILE SYSTEM</span>
          <i className="mobile-transition-accent" />
          <i className="mobile-transition-velocity-rule" />
          <span className="mobile-transition-frame" aria-hidden="true"><i /><i /><i /><i /></span>
        </div>
      ))}
    </div>
  );
}
