import { useLayoutEffect } from "react";
import { gsap } from "gsap";
import { CustomEase } from "gsap/CustomEase";
import { ScrollTrigger } from "gsap/ScrollTrigger";

const transitionTargets = [
  ".editorial-intro",
  ".workflow-section",
  ".evidence-section",
];

const transitionLabels = [
  "FILE 01 / UNDERSTANDING",
  "FILE 04 / WORKFLOW",
  "FILE 05 / EVIDENCE",
];

export default function ScrollDirector() {
  useLayoutEffect(() => {
    gsap.registerPlugin(ScrollTrigger, CustomEase);

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const desktop = window.matchMedia("(min-width: 1024px)").matches;
    if (reducedMotion || !desktop) return undefined;

    document.documentElement.classList.add("scroll-directed");
    const updateScrollTrigger = () => ScrollTrigger.update();
    window.addEventListener("juris:lenis-scroll", updateScrollTrigger);

    const context = gsap.context(() => {
      const mechanicalEase = CustomEase.create("jurisMechanical", "M0,0 C0.55,0 0.18,1 1,1");
      const archiveLayers = gsap.utils.toArray<HTMLElement>(".hero-archive-layer");
      const machinePanels = gsap.utils.toArray<HTMLElement>(".hero-machine-panel");
      const machineContent = gsap.utils.toArray<HTMLElement>(".hero-interface-content");
      const machineInterface = document.querySelector<HTMLElement>(".hero-constructed-interface");
      const machineScanner = document.querySelector<HTMLElement>(".hero-machine-scanner");
      const confidenceNumber = document.querySelector<HTMLElement>(".hero-machine-confidence strong");
      const archiveCover = document.querySelector<HTMLElement>(".hero-monolith-cover");
      const archiveCoverDetails = gsap.utils.toArray<HTMLElement>(
        ".hero-archive-cover-meta > *, .hero-archive-data > *, .hero-archive-clauses > *",
      );
      const archiveIndex = gsap.utils.toArray<HTMLElement>(".hero-archive-index li");
      const archiveRegistrationLine = document.querySelector<HTMLElement>(".hero-archive-registration-line");
      const archiveScan = document.querySelector<HTMLElement>(".hero-archive-scan");
      const heroTimeline = gsap.timeline({
        scrollTrigger: {
          trigger: ".hero",
          start: "top top",
          end: () => `+=${Math.max(window.innerHeight * 3.2, 2200)}`,
          pin: true,
          scrub: 1.05,
          anticipatePin: 1,
          invalidateOnRefresh: true,
          refreshPriority: 20,
        },
      });

      heroTimeline
        .fromTo(archiveCoverDetails, { clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0% 0 0)", duration: 0.42, stagger: 0.025, ease: mechanicalEase }, 0)
        .fromTo(archiveRegistrationLine, { scaleX: 0 }, { scaleX: 1, transformOrigin: "left center", duration: 0.58, ease: mechanicalEase }, 0.12)
        .fromTo(archiveIndex, { xPercent: 100 }, { xPercent: 0, duration: 0.36, stagger: 0.04, ease: mechanicalEase }, 0.16)
        .fromTo(archiveScan, { scaleY: 0, yPercent: -100 }, { scaleY: 1, yPercent: 0, transformOrigin: "top center", duration: 0.18, ease: mechanicalEase }, 0.22)
        .to(archiveScan, { yPercent: 4800, duration: 0.64, ease: "none" }, 0.4)
        .to(archiveCover, { clipPath: "inset(0 0 0 0)", duration: 0.01 }, 0)
        .to(".hero-title", { scale: 0.985, yPercent: -1.2, transformOrigin: "left center", duration: 1.05, ease: mechanicalEase }, 0.48)
        .to(archiveCoverDetails, { clipPath: "inset(0 0 100% 0)", duration: 0.34, stagger: { each: 0.008, from: "end" }, ease: mechanicalEase }, 0.86)
        .to(archiveIndex, { xPercent: 120, duration: 0.28, stagger: 0.025, ease: mechanicalEase }, 0.9)
        .to(archiveCover, { clipPath: "inset(0 0 100% 0)", duration: 0.42, ease: mechanicalEase }, 0.98)
        .to(archiveLayers, {
          y: (index) => (index - (archiveLayers.length - 1) / 2) * 1.05,
          duration: 1.18,
          stagger: { each: 0.0025, from: "center" },
          ease: mechanicalEase,
        }, 0.18)
        .to(".hero-monolith", { scaleX: 1.38, scaleY: 0.88, xPercent: -18, duration: 1.02, ease: mechanicalEase }, 0.92)
        .to(archiveLayers, {
          xPercent: (index) => index % 5 === 0 ? -44 : index % 5 === 4 ? 44 : 0,
          scaleX: (index) => index % 5 === 0 ? 0.31 : index % 5 === 4 ? 0.4 : 0.62,
          transformOrigin: (index) => index % 5 === 0 ? "left center" : index % 5 === 4 ? "right center" : "center center",
          duration: 1.08,
          stagger: { each: 0.0018, from: "edges" },
          ease: mechanicalEase,
        }, 1.08)
        .fromTo(machinePanels, { scaleX: 0 }, { scaleX: 1, duration: 0.72, stagger: 0.08, transformOrigin: "left center", ease: mechanicalEase }, 1.38)
        .to(archiveLayers, {
          xPercent: (index) => index % 5 === 0 ? -128 : index % 5 === 4 ? 128 : 0,
          scaleX: (index) => index % 5 === 0 || index % 5 === 4 ? 0.14 : 0.015,
          duration: 0.72,
          stagger: { each: 0.0012, from: "center" },
          ease: mechanicalEase,
        }, 1.86)
        .to(".hero-monolith", { scaleX: 0.015, duration: 0.62, ease: mechanicalEase }, 1.9)
        .fromTo(machineScanner, { scaleY: 0, x: 0 }, { scaleY: 1, x: 0, duration: 0.28, transformOrigin: "top center", ease: mechanicalEase }, 2.34)
        .fromTo(machineContent[0], { clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0% 0 0)", duration: 0.3, ease: "none" }, 2.58)
        .fromTo(machineContent[1], { clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0% 0 0)", duration: 0.84, ease: "none" }, 2.82)
        .fromTo(machineContent[2], { clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0% 0 0)", duration: 0.46, ease: "none" }, 3.62)
        .to(machineScanner, { x: () => Math.max(0, (machineInterface?.offsetWidth || 0) - 2), duration: 1.5, ease: "none" }, 2.58)
        .to(".hero-bottom-grid", { yPercent: -12, duration: 0.72, ease: mechanicalEase }, 3.45)
        .to(".hero-rule", { y: -22, duration: 0.55, ease: mechanicalEase }, 3.55)
        .to(".hero-scroll-cue", { x: 80, duration: 0.55, ease: mechanicalEase }, 3.55)
        .to(".hero-title", { yPercent: -10, clipPath: "inset(0 0 100% 0)", duration: 0.48, ease: mechanicalEase }, 4.0);

      if (confidenceNumber) {
        heroTimeline.fromTo(confidenceNumber, { textContent: 0 }, { textContent: 97, snap: { textContent: 1 }, duration: 0.42, ease: "none" }, 3.7);
      }

      transitionTargets.forEach((selector, index) => {
        const section = document.querySelector(selector);
        const sheet = document.querySelector(`.case-transition-sheet[data-sheet="${index}"]`);
        if (!section || !sheet) return;

        // Keep GSAP as the single owner of the sheet transform. Mixing a CSS
        // translateY with yPercent leaves a retained pixel offset in GSAP.
        gsap.set(sheet, { y: 0, yPercent: 102 });
        const transition = gsap.timeline({
          scrollTrigger: {
            trigger: section,
            start: "top 98%",
            end: "top 8%",
            scrub: 0.75,
          },
        });

        transition
          .fromTo(section, { y: 130, clipPath: "inset(14% 0 0 0)" }, { y: 0, clipPath: "inset(0% 0 0 0)", ease: "none", duration: 1 }, 0)
          .to(sheet, { y: 0, yPercent: 0, ease: "none", duration: 0.48 }, 0)
          .to(sheet, { y: 0, yPercent: -102, ease: "none", duration: 0.52 }, 0.48);
      });

      gsap.to(".editorial-statement h2", {
        scale: 1.3,
        xPercent: -7,
        transformOrigin: "left center",
        ease: "none",
        scrollTrigger: {
          trigger: ".editorial-intro",
          start: "top 48%",
          end: "bottom 42%",
          scrub: 1,
        },
      });

      gsap.utils.toArray<HTMLElement>(".capability-line").forEach((row, index) => {
        gsap.fromTo(
          row,
          { xPercent: index % 2 === 0 ? 12 : -12, scaleX: 0.86 },
          {
            xPercent: 0,
            scaleX: 1,
            transformOrigin: index % 2 === 0 ? "right center" : "left center",
            ease: "none",
            scrollTrigger: { trigger: row, start: "top 92%", end: "top 52%", scrub: 0.8 },
          },
        );
      });

      const transformationSection = document.querySelector<HTMLElement>(".transformation-section");
      const transformationPin = document.querySelector<HTMLElement>(".transformation-pin");
      const transformationRaw = document.querySelector<HTMLElement>(".transformation-raw");
      const transformationRail = document.querySelector<HTMLElement>(".transformation-rail");
      const transformationDecision = document.querySelector<HTMLElement>(".transformation-decision");
      const transformationDecisionContent = document.querySelector<HTMLElement>(".transformation-decision-content");
      const transformationRecommendation = document.querySelector<HTMLElement>(".transformation-recommendation");
      const transformationConfidence = document.querySelector<HTMLElement>(".transformation-confidence");
      const transformationEntryRule = document.querySelector<HTMLElement>(".transformation-entry-rule");
      const transformationExitRule = document.querySelector<HTMLElement>(".transformation-exit-rule");
      const transformationMarks = gsap.utils.toArray<HTMLElement>(".transformation-raw mark");
      const transformationConnectors = gsap.utils.toArray<HTMLElement>(".transformation-connectors i");
      const transformationRailItems = gsap.utils.toArray<HTMLElement>(".transformation-rail dl > div");

      if (
        transformationSection && transformationPin && transformationRaw && transformationRail
        && transformationDecision && transformationDecisionContent && transformationRecommendation
        && transformationConfidence && transformationEntryRule && transformationExitRule
      ) {
        let transformationIndex = -1;
        const transformationTimeline = gsap.timeline({
          scrollTrigger: {
            trigger: transformationSection,
            start: "top top",
            end: () => `+=${Math.max(window.innerHeight * 1.05, 820)}`,
            pin: transformationPin,
            scrub: 0.8,
            anticipatePin: 1,
            invalidateOnRefresh: true,
            refreshPriority: 10,
            onUpdate: ({ progress }) => {
              const next = Math.min(3, Math.floor(progress * 4));
              if (next === transformationIndex) return;
              transformationIndex = next;
              window.dispatchEvent(new CustomEvent("juris:transformation-step", { detail: next }));
            },
          },
        });

        transformationTimeline
          .fromTo(transformationEntryRule, { scaleX: 0.16 }, { scaleX: 1, duration: 0.24, ease: "none" }, 0)
          .fromTo(transformationRaw, { y: 24, scaleY: 0.96 }, { y: 0, scaleY: 1, transformOrigin: "top center", duration: 0.28, ease: mechanicalEase }, 0)
          .fromTo(transformationMarks, { boxShadow: "inset 0 -1px 0 rgba(196,77,49,.9)" }, { boxShadow: "inset 0 -1.25em 0 rgba(196,77,49,.26)", duration: 0.2, stagger: 0.06, ease: "none" }, 0.24)
          .fromTo(transformationConnectors, { scaleX: 0 }, { scaleX: 1, transformOrigin: "left center", duration: 0.28, stagger: 0.055, ease: "none" }, 0.28)
          .fromTo(transformationRail, { scaleY: 0.08 }, { scaleY: 1, transformOrigin: "top center", duration: 0.3, ease: mechanicalEase }, 0.34)
          .fromTo(transformationRailItems, { opacity: 0, clipPath: "inset(0 100% 0 0)" }, { opacity: 1, clipPath: "inset(0 0% 0 0)", duration: 0.2, stagger: 0.055, ease: "none" }, 0.45)
          .fromTo(transformationConfidence, { textContent: 0 }, { textContent: 97, snap: { textContent: 1 }, duration: 0.26, ease: "none" }, 0.56)
          .fromTo(transformationDecisionContent, { clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0% 0 0)", duration: 0.3, ease: mechanicalEase }, 0.72)
          .fromTo(transformationRecommendation, { y: 18, opacity: 0 }, { y: 0, opacity: 1, duration: 0.2, ease: mechanicalEase }, 0.82)
          .to(transformationDecision, { scaleX: 1.025, transformOrigin: "right center", duration: 0.22, ease: mechanicalEase }, 0.94)
          .fromTo(transformationExitRule, { scaleY: 0 }, { scaleY: 1, transformOrigin: "top center", duration: 0.2, ease: "none" }, 0.96);
      }

      gsap.utils.toArray<HTMLElement>(".feature-row").forEach((row, index) => {
        gsap.fromTo(
          row,
          { xPercent: index % 2 ? 18 : -18, rotateY: index % 2 ? -4 : 4 },
          {
            xPercent: 0,
            rotateY: 0,
            ease: "none",
            scrollTrigger: { trigger: row, start: "top 94%", end: "top 58%", scrub: 0.8 },
          },
        );
      });

      const workflow = document.querySelector<HTMLElement>(".workflow-section");
      const timeline = document.querySelector<HTMLElement>(".timeline");
      if (workflow && timeline) {
        let workflowIndex = -1;
        const distance = () => Math.max(0, timeline.scrollWidth - window.innerWidth + 120);
        gsap.to(timeline, {
          x: () => -distance(),
          ease: "none",
          scrollTrigger: {
            trigger: workflow,
            start: "top top",
            end: () => `+=${distance() + window.innerHeight * 1.2}`,
            pin: true,
            scrub: 0.9,
            invalidateOnRefresh: true,
            anticipatePin: 1,
            onUpdate: ({ progress }) => {
              const next = Math.min(5, Math.floor(progress * 6));
              if (next === workflowIndex) return;
              workflowIndex = next;
              window.dispatchEvent(new CustomEvent("juris:workflow-step", { detail: next }));
            },
          },
        });
      }

      const evidenceTimeline = gsap.timeline({
        scrollTrigger: {
          trigger: ".evidence-section",
          start: "top top",
          end: "+=135%",
          pin: true,
          scrub: 0.9,
          anticipatePin: 1,
        },
      });
      evidenceTimeline
        .to(".evidence-heading h2", { scale: 2.35, xPercent: -18, yPercent: 5, transformOrigin: "center center", ease: "none" }, 0)
        .fromTo(".evidence-strip article", { yPercent: 105 }, { yPercent: 0, stagger: 0.08, ease: "none" }, 0.12);

      const caseFileStage = document.querySelector<HTMLElement>(".casefile-stage");
      const caseFileCover = document.querySelector<HTMLElement>(".casefile-cover");
      const caseFileWorkspace = document.querySelector<HTMLElement>(".casefile-workspace");
      const caseFileTabs = document.querySelector<HTMLElement>(".casefile-tabs");
      const caseFileReader = document.querySelector<HTMLElement>(".casefile-reader");
      const caseFileIntelligence = document.querySelector<HTMLElement>(".casefile-intelligence");
      const documentPage = document.querySelector<HTMLElement>(".casefile-document");
      const documentContent = document.querySelector<HTMLElement>(".casefile-document-content");
      const processingStage = document.querySelector<HTMLElement>(".casefile-processing-stage");
      const processingFragments = gsap.utils.toArray<HTMLElement>(".casefile-process-fragment");
      const processingLocks = gsap.utils.toArray<HTMLElement>(".casefile-process-lock");
      const processingConnectors = gsap.utils.toArray<HTMLElement>(".casefile-process-connector");
      const processingMilestones = gsap.utils.toArray<HTMLElement>(".casefile-processing-foot i");
      const processingConfidence = document.querySelector<HTMLElement>(".casefile-process-confidence-value");
      const scanLine = document.querySelector<HTMLElement>(".casefile-scan-line");
      const exitSheet = document.querySelector<HTMLElement>(".casefile-exit-sheet");
      const exitSheetDetails = gsap.utils.toArray<HTMLElement>(".casefile-exit-sheet > *");

      if (
        caseFileStage && caseFileCover && caseFileWorkspace && caseFileTabs && caseFileReader
        && caseFileIntelligence && documentPage && documentContent && processingStage && scanLine && exitSheet
      ) {
        const confidence = document.querySelector<HTMLElement>(".casefile-confidence");
        const confidenceNumber = document.querySelector<HTMLElement>(".casefile-confidence-number");
        const confidenceBar = document.querySelector<HTMLElement>(".casefile-confidence > i > b");
        const entities = document.querySelector<HTMLElement>(".casefile-entities");
        const clauses = document.querySelector<HTMLElement>(".casefile-clauses");
        const clauseCount = document.querySelector<HTMLElement>(".casefile-clause-count");
        const clauseRows = gsap.utils.toArray<HTMLElement>(".casefile-clause-row");
        const risk = document.querySelector<HTMLElement>(".casefile-risk");
        const riskNumber = document.querySelector<HTMLElement>(".casefile-risk-number");
        const answer = document.querySelector<HTMLElement>(".casefile-answer");
        const processStatus = document.querySelector<HTMLElement>(".casefile-process-status");
        const coverTitle = document.querySelector<HTMLElement>(".casefile-cover-title");
        const convergenceOffset = (fragment: HTMLElement, axis: "x" | "y") => {
          const fragmentRect = fragment.getBoundingClientRect();
          const pageRect = documentPage.getBoundingClientRect();
          if (axis === "x") return pageRect.left + pageRect.width / 2 - (fragmentRect.left + fragmentRect.width / 2);
          return pageRect.top + pageRect.height / 2 - (fragmentRect.top + fragmentRect.height / 2);
        };
        let caseFileIndex = -1;

        const caseFileTimeline = gsap.timeline({
          scrollTrigger: {
            trigger: caseFileStage,
            start: "top top",
            end: () => `+=${Math.max(window.innerHeight * 6.2, 4300)}`,
            pin: true,
            scrub: 1.1,
            anticipatePin: 1,
            invalidateOnRefresh: true,
            onUpdate: ({ progress }) => {
              const next = progress >= 0.64 ? 4 : progress >= 0.52 ? 3 : progress >= 0.38 ? 2 : progress >= 0.28 ? 1 : 0;
              if (next === caseFileIndex) return;
              caseFileIndex = next;
              window.dispatchEvent(new CustomEvent("juris:casefile-step", { detail: next }));
            },
          },
        });

        caseFileTimeline
          .set(processStatus, { textContent: "INGESTING" }, 0)
          .set(documentPage, { opacity: 0 }, 0)
          .fromTo(caseFileCover, { scale: 0.78, yPercent: 18, rotateX: 4 }, { scale: 1, yPercent: 0, rotateX: 0, duration: 0.72, ease: "none" }, 0)
          .to(coverTitle, { scale: 1.16, xPercent: -4, transformOrigin: "left center", duration: 0.72, ease: "none" }, 0)
          .fromTo(caseFileWorkspace, { clipPath: "inset(0 49% 0 49%)" }, { clipPath: "inset(0 0% 0 0%)", duration: 0.92, ease: "none" }, 0.68)
          .fromTo(caseFileTabs, { rotateY: -88 }, { rotateY: 0, transformOrigin: "right center", duration: 0.82, ease: "none" }, 0.72)
          .fromTo(caseFileReader, { scaleX: 0.08 }, { scaleX: 1, transformOrigin: "left center", duration: 0.86, ease: "none" }, 0.74)
          .fromTo(caseFileIntelligence, { rotateY: 88 }, { rotateY: 0, transformOrigin: "left center", duration: 0.82, ease: "none" }, 0.82)
          .to(caseFileCover, { rotateY: -96, xPercent: -20, transformOrigin: "left center", duration: 0.94, ease: "none" }, 0.68)
          .to(caseFileCover, { xPercent: -118, duration: 0.42, ease: "none" }, 1.34)
          .set(processStatus, { textContent: "DOCUMENT / PARSED" }, 1.02)
          .fromTo(processingStage, { opacity: 0, clipPath: "inset(48% 0 48% 0)" }, { opacity: 1, clipPath: "inset(0% 0 0% 0)", duration: 0.38, ease: "none" }, 1.02)
          .fromTo(processingFragments, {
            opacity: 0,
            x: (index) => index % 2 === 0 ? -48 - index * 3 : 48 + index * 3,
            y: (index) => index % 3 === 0 ? -30 : index % 3 === 1 ? 22 : 44,
            rotation: (index) => index % 2 === 0 ? -3 : 3,
            scale: 0.86,
          }, {
            opacity: 1,
            x: 0,
            y: 0,
            rotation: (index) => [-1, 1, -1.2, 1.3, -.8, -1.4, .8, .6][index] || 0,
            scale: 1,
            duration: 0.58,
            stagger: 0.055,
            ease: "none",
          }, 1.12)
          .fromTo(processingConnectors, { scaleX: 0 }, { scaleX: 1, duration: 0.42, stagger: 0.08, transformOrigin: "left center", ease: "none" }, 1.26)
          .fromTo(processingLocks, { scale: 0.35, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.38, stagger: 0.1, ease: "none" }, 1.34)
          .fromTo(processingMilestones, { scaleX: 0 }, { scaleX: 1, duration: 0.3, stagger: 0.08, transformOrigin: "left center", ease: "none" }, 1.42)
          .set(processStatus, { textContent: "ENTITIES / LINKING" }, 1.66)
          .set(processStatus, { textContent: "STRUCTURE / ALIGNING" }, 2.02)
          .to(processingConnectors, { scaleX: 0, transformOrigin: "right center", duration: 0.36, stagger: 0.04, ease: "none" }, 2.02)
          .to(processingLocks, { scale: 0.2, opacity: 0, duration: 0.42, stagger: 0.06, ease: "none" }, 2.08)
          .to(processingFragments, {
            x: (_index, target) => convergenceOffset(target as HTMLElement, "x"),
            y: (_index, target) => convergenceOffset(target as HTMLElement, "y"),
            rotation: 0,
            scale: 0.62,
            opacity: 0.28,
            duration: 0.7,
            stagger: 0.025,
            ease: "none",
          }, 2.04)
          .to(documentPage, { opacity: 1, duration: 0.5, ease: "none" }, 2.2)
          .to(processingStage, { scaleX: 0.74, scaleY: 0.94, opacity: 0, transformOrigin: "center center", duration: 0.7, ease: "none" }, 2.18)
          .set(processingStage, { visibility: "hidden" }, 2.9)
          .set(processStatus, { textContent: "OCR / READING" }, 2.38)
          .fromTo(documentContent, { clipPath: "inset(0 0 100% 0)" }, { clipPath: "inset(0 0 0% 0)", duration: 1.9, ease: "none" }, 2.4)
          .fromTo(scanLine, { y: 0 }, { y: () => Math.max(0, documentPage.offsetHeight - 92), duration: 1.9, ease: "none" }, 2.4)
          .fromTo(confidence, { clipPath: "inset(0 0 100% 0)", y: 24 }, { clipPath: "inset(0 0 0% 0)", y: 0, duration: 0.45, ease: "none" }, 2.72)
          .fromTo(entities, { clipPath: "inset(0 0 100% 0)", y: 24 }, { clipPath: "inset(0 0 0% 0)", y: 0, duration: 0.5, ease: "none" }, 3.05)
          .set(processStatus, { textContent: "CLAUSES / INDEXING" }, 3.32)
          .fromTo(clauses, { clipPath: "inset(0 0 100% 0)", y: 24 }, { clipPath: "inset(0 0 0% 0)", y: 0, duration: 0.55, ease: "none" }, 3.36)
          .fromTo(clauseRows, { clipPath: "inset(0 100% 0 0)", x: 18 }, { clipPath: "inset(0 0% 0 0)", x: 0, duration: 0.28, stagger: 0.13, ease: "none" }, 3.6)
          .to(documentPage, { yPercent: -9, duration: 1.25, ease: "none" }, 4.02)
          .set(processStatus, { textContent: "RISK / ANALYZING" }, 4.18)
          .fromTo(risk, { clipPath: "inset(0 0 100% 0)", y: 24 }, { clipPath: "inset(0 0 0% 0)", y: 0, duration: 0.58, ease: "none" }, 4.22)
          .to(scanLine, { scaleX: 0, transformOrigin: "right center", duration: 0.32, ease: "none" }, 4.86)
          .set(processStatus, { textContent: "REVIEW / READY" }, 4.95)
          .fromTo(answer, { clipPath: "inset(0 0 100% 0)", y: 28 }, { clipPath: "inset(0 0 0% 0)", y: 0, duration: 0.72, ease: "none" }, 4.98)
          .fromTo(exitSheet, { yPercent: 118, scale: 0.42 }, { yPercent: 0, scale: 0.42, duration: 0.58, ease: "none" }, 5.76)
          .to(caseFileWorkspace, { scale: 0.94, yPercent: -3, duration: 1.18, ease: "none" }, 5.76)
          .to(exitSheetDetails, { clipPath: "inset(0 100% 0 0)", xPercent: -12, duration: 0.32, ease: "none" }, 6.1)
          .to(exitSheet, { scale: 3.6, duration: 1.18, ease: "none" }, 6.18)
          .set([exitSheet, caseFileWorkspace], { visibility: "hidden" }, 7.36);

        if (confidenceNumber) {
          caseFileTimeline.fromTo(confidenceNumber, { textContent: 0 }, { textContent: 97, snap: { textContent: 1 }, duration: 0.82, ease: "none" }, 2.76);
        }
        if (confidenceBar) {
          caseFileTimeline.fromTo(confidenceBar, { scaleX: 0 }, { scaleX: 0.97, transformOrigin: "left center", duration: 0.82, ease: "none" }, 2.76);
        }
        if (clauseCount) {
          caseFileTimeline.fromTo(clauseCount, { textContent: 0 }, { textContent: 12, snap: { textContent: 1 }, duration: 0.72, ease: "none" }, 3.42);
        }
        if (riskNumber) {
          caseFileTimeline.fromTo(riskNumber, { textContent: 0 }, { textContent: 3, snap: { textContent: 1 }, duration: 0.62, ease: "none" }, 4.28);
        }
        if (processingConfidence) {
          caseFileTimeline.fromTo(processingConfidence, { textContent: 0 }, { textContent: 97, snap: { textContent: 1 }, duration: 0.62, ease: "none" }, 1.4);
        }
      }
    });

    const refresh = () => ScrollTrigger.refresh();
    document.fonts.ready.then(refresh);
    window.addEventListener("resize", refresh);

    return () => {
      context.revert();
      window.removeEventListener("resize", refresh);
      window.removeEventListener("juris:lenis-scroll", updateScrollTrigger);
      document.documentElement.classList.remove("scroll-directed");
    };
  }, []);

  return (
    <div className="case-transition-layer" aria-hidden="true">
      {transitionLabels.map((label, index) => (
        <div className="case-transition-sheet" data-sheet={index} key={label}>
          <span>{label}</span>
          <i className="registration-mark registration-mark-a" />
          <i className="registration-mark registration-mark-b" />
          <b>{String(index + 1).padStart(2, "0")}</b>
        </div>
      ))}
    </div>
  );
}
