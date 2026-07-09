import React from "react";
import { Analytics } from "@vercel/analytics/react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import App from "./App.jsx";
import SignIn from "./pages/SignIn.jsx";
import CreateAccount from "./pages/CreateAccount.jsx";
import ForgotPassword from "./pages/ForgotPassword.jsx";
import ResetPassword from "./pages/ResetPassword.jsx";
import UploadDocument from "./pages/UploadDocument.jsx";
import Documents from "./pages/Documents.jsx";
import DocumentWorkspace from "./pages/DocumentWorkspace.jsx";
import { ThemeProvider } from "./components/ThemeProvider.jsx";
import { AuthProvider } from "./components/AuthProvider.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<App />} />
            <Route path="/sign-in" element={<SignIn />} />
            <Route path="/create-account" element={<CreateAccount />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route path="/upload-document" element={<UploadDocument />} />
            <Route path="/documents" element={<Documents />} />
            <Route path="/documents/:documentId/workspace" element={<DocumentWorkspace />} />
          </Routes>
        </BrowserRouter>
        <Analytics />
      </AuthProvider>
    </ThemeProvider>
  </React.StrictMode>,
);
