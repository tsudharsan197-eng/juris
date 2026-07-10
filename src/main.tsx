import React from "react";
import { Analytics } from "@vercel/analytics/react";
import { AnimatePresence, motion } from "framer-motion";
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
import { ThemeProvider } from "./components/ThemeProvider.jsx";
import { AuthProvider } from "./components/AuthProvider.jsx";
import ExperienceShell from "./components/ExperienceShell";
import "./styles.css";
import "./editorial.css";

function RoutedExperience() {
  const location = useLocation();

  return (
    <ExperienceShell>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={location.pathname}
          className="route-stage"
          initial={{ clipPath: "inset(0 0 100% 0)", y: 16 }}
          animate={{ clipPath: "inset(0 0 0% 0)", y: 0 }}
          exit={{ clipPath: "inset(100% 0 0 0)", y: -10 }}
          transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
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
          </Routes>
        </motion.div>
      </AnimatePresence>
      <Analytics />
    </ExperienceShell>
  );
}

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
