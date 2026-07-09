import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../components/AuthProvider.jsx";
import Button from "../components/Button.jsx";
import Navbar from "../components/Navbar.jsx";
import {
  normalizedContentType,
  uploadDocumentFile,
} from "../lib/documentsApi.js";

const MAX_FILE_SIZE = 25 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = [".pdf", ".doc", ".docx"];

export default function UploadDocument() {
  const navigate = useNavigate();
  const { isSignedIn, loading: authLoading } = useAuth();
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState("idle");
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [debugError, setDebugError] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const isLocked = !authLoading && !isSignedIn;
  const isInteractionDisabled = authLoading || isLocked || status === "uploading";

  const fileMeta = useMemo(() => {
    if (!file) return null;
    return {
      name: file.name,
      size: `${(file.size / (1024 * 1024)).toFixed(2)} MB`,
      type: normalizedContentType(file),
    };
  }, [file]);

  useEffect(() => {
    if (!isLocked) return;
    setFile(null);
    setProgress(0);
    setIsDragging(false);
    setDebugError(null);
    setStatus("locked");
    setMessage("Please sign in to upload documents.");
  }, [isLocked]);

  useEffect(() => {
    if (authLoading || !isSignedIn || status !== "locked") return;
    setStatus("idle");
    setMessage("");
  }, [authLoading, isSignedIn, status]);

  function validate(nextFile) {
    setStatus("validating");
    const extension = `.${nextFile.name.split(".").pop()?.toLowerCase()}`;
    if (!ACCEPTED_EXTENSIONS.includes(extension)) {
      throw new Error("Upload a PDF, DOC, or DOCX file.");
    }
    if (nextFile.size > MAX_FILE_SIZE) {
      throw new Error("File must be 25MB or smaller.");
    }
  }

  function showLockedMessage() {
    setIsDragging(false);
    setFile(null);
    setProgress(0);
    setDebugError(null);
    setStatus("locked");
    setMessage(authLoading ? "Checking your session..." : "Please sign in to upload documents.");
  }

  function selectFile(nextFile) {
    if (authLoading || isLocked) {
      showLockedMessage();
      return;
    }
    if (!nextFile) return;
    try {
      validate(nextFile);
      setFile(nextFile);
      setProgress(0);
      setMessage("File ready for secure upload.");
      setDebugError(null);
      setStatus("idle");
    } catch (error) {
      setFile(null);
      setProgress(0);
      setMessage(error.message);
      setDebugError(null);
      setStatus("error");
    }
  }

  async function uploadDocument() {
    if (authLoading || isLocked) {
      showLockedMessage();
      return;
    }

    if (!file) {
      setStatus("error");
      setMessage("Choose a file before uploading.");
      return;
    }

    try {
      validate(file);
      setStatus("uploading");
      setProgress(8);
      setDebugError(null);
      setMessage("Uploading through the secure Juris backend...");
      await uploadDocumentFile(file, setProgress);

      setStatus("uploaded");
      setProgress(100);
      setMessage("Document uploaded. Opening workspace...");
      window.setTimeout(() => navigate("/documents"), 650);
    } catch (error) {
      setStatus("error");
      setMessage(error.detail || error.message);
      setDebugError(
        error.backendError
          ? {
              type: error.backendType || "Error",
              error: error.backendError,
            }
          : null,
      );
    }
  }

  function handleDrop(event) {
    event.preventDefault();
    if (authLoading || isLocked) {
      showLockedMessage();
      return;
    }
    setIsDragging(false);
    selectFile(event.dataTransfer.files?.[0]);
  }

  function openFilePicker() {
    if (authLoading || isLocked) {
      showLockedMessage();
      return;
    }
    inputRef.current?.click();
  }

  return (
    <>
      <Navbar />
      <main className="upload-page">
        <section className="upload-shell">
          <div className="upload-copy reveal">
            <p className="eyebrow">Secure document intake</p>
            <h1>Upload a legal document.</h1>
            <p>
              Juris sends files to a secure FastAPI upload endpoint. The backend verifies your
              session, stores the file in private Cloudflare R2, and records document metadata.
            </p>
          </div>

          <div className="upload-card-shell reveal delay-1">
            {isLocked && (
              <div className="upload-auth-lock" role="status">
                <span>Authentication required</span>
                <p>Please sign in to upload documents.</p>
                <Button to="/sign-in" variant="secondary">Sign in</Button>
              </div>
            )}

            <div
              className={`upload-zone ${isDragging ? "dragging" : ""} ${isInteractionDisabled ? "disabled" : ""}`}
              onClick={openFilePicker}
              onDragOver={(event) => {
                event.preventDefault();
                if (authLoading || isLocked) {
                  showLockedMessage();
                  return;
                }
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              role="button"
              tabIndex={isInteractionDisabled ? -1 : 0}
              aria-disabled={isInteractionDisabled}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  openFilePicker();
                }
              }}
            >
              <input
                ref={inputRef}
                type="file"
                disabled={isInteractionDisabled}
                accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={(event) => selectFile(event.target.files?.[0])}
              />
              <span className="upload-mark">+</span>
              <h2>{isLocked ? "Sign in to upload" : "Drop PDF, DOC, or DOCX here"}</h2>
              <p>{isLocked ? "Please sign in to upload documents." : "Maximum size: 25MB. Files are uploaded with user-scoped object keys."}</p>
            </div>

            {fileMeta && (
              <article className="selected-file" aria-label="Selected file preview">
                <div>
                  <span>Selected file</span>
                  <strong>{fileMeta.name}</strong>
                </div>
                <div>
                  <span>{fileMeta.size}</span>
                  <span>{fileMeta.type}</span>
                </div>
              </article>
            )}

            <div className="upload-progress" aria-label={`Upload progress ${progress}%`}>
              <span style={{ width: `${progress}%` }} />
            </div>

            <div className={`upload-status ${status}`}>
              <span>{status}</span>
              <p>{message || "Waiting for a document."}</p>
              {debugError && (
                <code className="upload-error-debug">
                  {debugError.type}: {debugError.error}
                </code>
              )}
            </div>

            <div className="upload-actions">
              <Button type="button" onClick={uploadDocument} disabled={isInteractionDisabled}>
                {status === "uploading" ? "Uploading..." : "Upload Document"}
              </Button>
              <Button type="button" variant="secondary" onClick={openFilePicker} disabled={isInteractionDisabled}>
                Choose File
              </Button>
            </div>
          </div>
        </section>
      </main>
    </>
  );
}
