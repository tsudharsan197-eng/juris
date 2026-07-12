import { motion } from "framer-motion";
import { ArrowDown, ShieldCheck } from "lucide-react";
import Button from "../components/Button.jsx";
import { useAuth } from "../components/AuthProvider.jsx";
import HeroArchive from "../components/HeroArchive";
import useMediaQuery from "../hooks/useMediaQuery";

export default function Hero() {
  const { user, isSignedIn } = useAuth();
  const userName = displayName(user);
  const isMobile = useMediaQuery("(max-width: 1023px)");
  const activeLockup = isMobile ? mobileLockup : lockup;
  const activeLineReveal = isMobile ? mobileLineReveal : lineReveal;

  return (
    <section className="hero section-shell">
      <div className="hero-scene" aria-hidden="true">
        <HeroArchive />
      </div>

      <div className="hero-rule hero-rule-top" aria-hidden="true">
        <span>JURIS / LEGAL INTELLIGENCE</span>
        <span>EST. 2026</span>
        <span>37.7749 N</span>
      </div>

      <motion.div className="hero-lockup" initial="hidden" animate="visible" variants={activeLockup}>
        {isSignedIn && (
          <motion.div className="hero-greeting" variants={activeLineReveal}>
            <span>Welcome back</span><strong>{userName}</strong>
          </motion.div>
        )}
        <motion.p className="hero-kicker" variants={activeLineReveal}>From documents to decisions.</motion.p>
        <div className="hero-title-stage">
          <h1 className="hero-title hero-title-back">
            <motion.span variants={activeLineReveal}>Legal documents</motion.span>
            <motion.span variants={activeLineReveal}>become <em>legal</em></motion.span>
            <motion.span className="hero-title-last" variants={activeLineReveal}>intelligence.</motion.span>
          </h1>
          <h1 className="hero-title hero-title-foreground" aria-hidden="true">
            <span>Legal documents</span>
            <span>become <em>legal</em></span>
            <span className="hero-title-last">intelligence.</span>
          </h1>
        </div>
      </motion.div>

      <div className="hero-bottom-grid">
        <motion.div
          className="hero-intro"
          initial={isMobile ? { clipPath: "inset(0 0 100% 0)", y: 28 } : { clipPath: "inset(0 100% 0 0)" }}
          animate={isMobile ? { clipPath: "inset(0 0 0% 0)", y: 0 } : { clipPath: "inset(0 0% 0 0)" }}
          transition={isMobile ? { delay: .48, duration: .68, ease: [.25, .8, .25, 1] } : { delay: .65, duration: 1.1 }}
        >
          <p>Upload contracts. Find clauses. Surface risk. Compare versions. Ask precise questions and get source-grounded answers.</p>
          <div className="hero-actions">
            <Button to={isSignedIn ? "/upload-document" : "/create-account"}>{isSignedIn ? "Upload Documents" : "Create Account"}</Button>
            <Button href="#what-is-juris" variant="secondary">Explore Juris</Button>
          </div>
        </motion.div>

        <div className="hero-specs" aria-label="Juris product capabilities">
          <div><span>01</span><strong>Private storage</strong><small><ShieldCheck size={13} /> User-scoped R2</small></div>
          <div><span>02</span><strong>Source-backed</strong><small>Chunk-level citations</small></div>
          <div><span>03</span><strong>AI analysis</strong><small>Clauses / Risk / Compare</small></div>
        </div>
      </div>

      <a className="hero-scroll-cue" href="#what-is-juris"><ArrowDown size={15} /> Index / 01</a>
    </section>
  );
}

const lockup = { hidden: {}, visible: { transition: { staggerChildren: 0.13, delayChildren: 0.12 } } };
const mobileLockup = { hidden: {}, visible: { transition: { staggerChildren: .085, delayChildren: .06 } } };
const lineReveal = {
  hidden: { clipPath: "inset(0 0 100% 0)", y: 56, rotateX: -8 },
  visible: { clipPath: "inset(0 0 0% 0)", y: 0, rotateX: 0, transition: { duration: 1.05, ease: [0.22, 1, 0.36, 1] } },
};
const mobileLineReveal = {
  hidden: { clipPath: "inset(0 0 100% 0)", y: 42, scaleY: .96 },
  visible: { clipPath: "inset(0 0 0% 0)", y: 0, scaleY: 1, transition: { duration: .72, ease: [.25, .8, .25, 1] } },
};

function displayName(user) {
  const metadata = user?.user_metadata || {};
  const name = metadata.full_name || metadata.name;
  if (name) return firstName(name);
  if (user?.email?.includes("@")) return user.email.split("@")[0];
  return "back";
}

function firstName(name) {
  return String(name).trim().split(/\s+/)[0] || "back";
}
