import { useLayoutEffect } from "react";
import { gsap } from "gsap";
import { CustomEase } from "gsap/CustomEase";
import { ScrollTrigger } from "gsap/ScrollTrigger";

const mobileScenes = [
  { selector: ".editorial-intro", number: "01", label: "UNDERSTANDING", tone: "blue" },
  { selector: ".transformation-section", number: "02", label: "TRANSFORMATION", tone: "rust" },
  { selector: ".feature-section", number: "03", label: "CAPABILITIES", tone: "blue" },
  { selector: ".workflow-section", number: "04", label: "PROCESS", tone: "rust" },
  { selector: ".evidence-section", number: "05", label: "EVIDENCE", tone: "lime" },
  { selector: ".casefile-section", number: "06", label: "PRODUCT SYSTEM", tone: "blue" },
  { selector: ".footer", number: "07", label: "JURIS / CONTINUE", tone: "rust" },
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
          const archiveDetails = gsap.utils.toArray<HTMLElement>(
            ".hero-archive-cover-head, .hero-archive-cover-meta, .hero-archive-cover-foot",
          );

          gsap.timeline({ defaults: { ease: mechanicalEase } })
            .fromTo(heroScene, { xPercent: 18, scale: .94, clipPath: "inset(0 0 100% 0)" }, { xPercent: 0, scale: 1, clipPath: "inset(0 0 0% 0)", duration: .82 }, .14)
            .fromTo(archiveDetails, { x: 22, clipPath: "inset(0 100% 0 0)" }, { x: 0, clipPath: "inset(0 0% 0 0)", duration: .48, stagger: .06 }, .38);

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
              .to(heroLockup, { yPercent: -12, scale: .97, transformOrigin: "left top", ease: "none", duration: 1 }, 0)
              .to(heroScene, { yPercent: -16, scale: .92, transformOrigin: "right center", ease: "none", duration: 1 }, 0)
              .to(heroBottom, { yPercent: -8, ease: "none", duration: .72 }, .22);

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
            const transition = gsap.timeline({
              scrollTrigger: {
                trigger: section,
                start: "top 98%",
                end: "top 34%",
                scrub: .58,
                invalidateOnRefresh: true,
              },
            });

            transition
              .fromTo(panel, { yPercent: 102 }, { yPercent: -102, duration: 1, ease: "none" }, 0)
              .fromTo(section, { y: 58, scale: .985, clipPath: "inset(9% 0 0 0)" }, { y: 0, scale: 1, clipPath: "inset(0% 0 0 0)", duration: .72, ease: mechanicalEase }, .26);

            if (folio) {
              transition.fromTo(folio, { x: -26, opacity: .25 }, { x: 0, opacity: 1, duration: .34, ease: mechanicalEase }, .48);
            }
          });

          const transformationSection = document.querySelector<HTMLElement>(".transformation-section");
          const transformationRaw = document.querySelector<HTMLElement>(".transformation-raw");
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
              .fromTo(transformationRail, { scaleY: .18, clipPath: "inset(0 0 82% 0)" }, { scaleY: 1, clipPath: "inset(0 0 0% 0)", transformOrigin: "top center", duration: .3, ease: mechanicalEase }, .4)
              .fromTo(transformationDecision, { xPercent: 14, clipPath: "inset(0 0 0 14%)" }, { xPercent: 0, clipPath: "inset(0 0 0 0%)", duration: .34, ease: mechanicalEase }, .64)
              .to(transformationRaw, { xPercent: -6, scale: .985, transformOrigin: "left center", duration: .24, ease: "none" }, .76);
          }

          gsap.utils.toArray<HTMLElement>(".feature-row").forEach((row) => {
            gsap.fromTo(row, { y: 56, clipPath: "inset(0 0 100% 0)", "--mobile-row-progress": 0 }, {
              y: 0,
              clipPath: "inset(0 0 0% 0)",
              "--mobile-row-progress": 1,
              ease: "none",
              scrollTrigger: { trigger: row, start: "top 94%", end: "top 58%", scrub: .42, invalidateOnRefresh: true },
            });
          });

          gsap.utils.toArray<HTMLElement>(".timeline-step").forEach((step, index) => {
            gsap.fromTo(step, { clipPath: "inset(0 0 100% 0)", opacity: .35 }, {
              clipPath: "inset(0 0 0% 0)",
              opacity: 1,
              ease: "none",
              scrollTrigger: {
                trigger: step,
                start: "top 92%",
                end: "top 56%",
                scrub: .38,
                invalidateOnRefresh: true,
              },
            });

            ScrollTrigger.create({
              trigger: step,
              start: "top 58%",
              end: "bottom 42%",
              invalidateOnRefresh: true,
              onEnter: () => window.dispatchEvent(new CustomEvent("juris:workflow-step", { detail: index })),
              onEnterBack: () => window.dispatchEvent(new CustomEvent("juris:workflow-step", { detail: index })),
            });
          });

          gsap.utils.toArray<HTMLElement>(".evidence-strip article").forEach((card, index) => {
            gsap.fromTo(card, { y: 68, clipPath: "inset(0 0 100% 0)" }, {
              y: 0,
              clipPath: "inset(0 0 0% 0)",
              ease: "none",
              scrollTrigger: { trigger: card, start: "top 94%", end: "top 56%", scrub: .44, invalidateOnRefresh: true },
              delay: index * .02,
            });
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

          gsap.fromTo(".footer-logo", { xPercent: -18, clipPath: "inset(0 100% 0 0)" }, {
            xPercent: 0,
            clipPath: "inset(0 0% 0 0)",
            ease: "none",
            scrollTrigger: { trigger: ".footer", start: "top 94%", end: "top 58%", scrub: .45, invalidateOnRefresh: true },
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
        <div className={`mobile-transition-panel tone-${scene.tone}`} data-scene={index} key={scene.selector}>
          <span>{scene.label}</span>
          <b>{scene.number}</b>
          <i />
        </div>
      ))}
    </div>
  );
}
