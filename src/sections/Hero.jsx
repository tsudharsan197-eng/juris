import { lazy, Suspense } from "react";
import { motion } from "framer-motion";
import { ArrowDown, ShieldCheck } from "lucide-react";
import Button from "../components/Button.jsx";
import { useAuth } from "../components/AuthProvider.jsx";

const HeroScene = lazy(() => import("../components/HeroScene"));

export default function Hero() {
  const { user, isSignedIn } = useAuth();
  const userName = displayName(user);

  return (
    <section className="hero section-shell">
      <Suspense fallback={<div className="hero-scene-fallback" aria-hidden="true" />}>
        <HeroScene />
      </Suspense>

      <div className="hero-rule hero-rule-top" aria-hidden="true">
        <span>JURIS / LEGAL INTELLIGENCE</span>
        <span>EST. 2026</span>
        <span>37.7749 N</span>
      </div>

      <motion.div className="hero-lockup" initial="hidden" animate="visible" variants={lockup}>
        {isSignedIn && (
          <motion.div className="hero-greeting" variants={lineReveal}>
            <span>Welcome back</span><strong>{userName}</strong>
          </motion.div>
        )}
        <motion.p className="hero-kicker" variants={lineReveal}>From documents to decisions.</motion.p>
        <h1 className="hero-title">
          <motion.span variants={lineReveal}>Legal documents</motion.span>
          <motion.span variants={lineReveal}>become <em>legal</em></motion.span>
          <motion.span className="hero-title-last" variants={lineReveal}>intelligence.</motion.span>
        </h1>
      </motion.div>

      <div className="hero-bottom-grid">
        <motion.div className="hero-intro" initial={{ clipPath: "inset(0 100% 0 0)" }} animate={{ clipPath: "inset(0 0% 0 0)" }} transition={{ delay: 0.65, duration: 1.1 }}>
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
const lineReveal = {
  hidden: { clipPath: "inset(0 0 100% 0)", y: 56, rotateX: -8 },
  visible: { clipPath: "inset(0 0 0% 0)", y: 0, rotateX: 0, transition: { duration: 1.05, ease: [0.22, 1, 0.36, 1] } },
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
