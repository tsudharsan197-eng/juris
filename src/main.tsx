import React from "react";
import { Analytics } from "@vercel/analytics/react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import App from "./App";
import SignIn from "./pages/SignIn.jsx";
import CreateAccount from "./pages/CreateAccount.jsx";
import ForgotPassword from "./pages/ForgotPassword.jsx";
import ResetPassword from "./pages/ResetPassword.jsx";
import UploadDocument from "./pages/UploadDocument.jsx";
import Documents from "./pages/Documents.jsx";
import DocumentWorkspace from "./pages/DocumentWorkspace.jsx";
import JurisCompassPage from "./pages/JurisCompassPage.jsx";
import { ThemeProvider } from "./components/ThemeProvider.jsx";
import { AuthProvider } from "./components/AuthProvider.jsx";
import ExperienceShell from "./components/ExperienceShell";
import useMediaQuery from "./hooks/useMediaQuery";
import "./styles.css";
import "./editorial.css";
import "./mobile.css";
import "./compass.css";
import "./workspace-modern.css";

function RoutedExperience() {
  const location = useLocation();
  const isMobile = useMediaQuery("(max-width: 1023px)");
  const reduceMotion = useReducedMotion();
  const routeMotion = reduceMotion ? reducedRouteMotion : isMobile ? mobileRouteMotion : desktopRouteMotion;

  return (
    <ExperienceShell>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={location.pathname}
          className="route-stage"
          initial={routeMotion.initial}
          animate={routeMotion.animate}
          exit={routeMotion.exit}
          transition={routeMotion.transition}
        >
          <Routes location={location}>
            <Route path="/" element={<App />} />
            <Route path="/sign-in" element={<SignIn />} />
            <Route path="/create-account" element={<CreateAccount />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route path="/upload-document" element={<UploadDocument />} />
            <Route path="/documents" element={<Documents />} />
            <Route path="/documents/:documentId/workspace" element={<DocumentWorkspace />} />
            <Route path="/juris-compass" element={<JurisCompassPage />} />
          </Routes>
        </motion.div>
      </AnimatePresence>
      <Analytics />
    </ExperienceShell>
  );
}

const desktopRouteMotion = {
  initial: { clipPath: "inset(0 0 100% 0)", y: 16 },
  animate: { clipPath: "inset(0 0 0% 0)", y: 0 },
  exit: { clipPath: "inset(100% 0 0 0)", y: -10 },
  transition: { duration: .55, ease: [0.22, 1, 0.36, 1] as const },
};

const mobileRouteMotion = {
  initial: { clipPath: "inset(0 0 100% 0)", y: 30, scale: .992 },
  animate: { clipPath: "inset(0 0 0% 0)", y: 0, scale: 1 },
  exit: { clipPath: "inset(100% 0 0 0)", y: -24, scale: .992 },
  transition: { duration: .46, ease: [0.25, .8, .25, 1] as const },
};

const reducedRouteMotion = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
  transition: { duration: .16, ease: "linear" as const },
};

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <RoutedExperience />
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  </React.StrictMode>,
);
