import { useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
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
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState("idle");
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [debugError, setDebugError] = useState(null);
  const [isDragging, setIsDragging] = useState(false);

  const fileMeta = useMemo(() => {
    if (!file) return null;
    return {
      name: file.name,
      size: `${(file.size / (1024 * 1024)).toFixed(2)} MB`,
      type: normalizedContentType(file),
    };
  }, [file]);

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

  function selectFile(nextFile) {
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
    setIsDragging(false);
    selectFile(event.dataTransfer.files?.[0]);
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
            <div
              className={`upload-zone ${isDragging ? "dragging" : ""}`}
              onClick={() => inputRef.current?.click()}
              onDragOver={(event) => {
                event.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              role="button"
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
              }}
            >
              <input
                ref={inputRef}
                type="file"
                accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={(event) => selectFile(event.target.files?.[0])}
              />
              <span className="upload-mark">+</span>
              <h2>Drop PDF, DOC, or DOCX here</h2>
              <p>Maximum size: 25MB. Files are uploaded with user-scoped object keys.</p>
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
              <Button type="button" onClick={uploadDocument} disabled={status === "uploading"}>
                {status === "uploading" ? "Uploading..." : "Upload Document"}
              </Button>
              <Button type="button" variant="secondary" onClick={() => inputRef.current?.click()}>
                Choose File
              </Button>
            </div>
          </div>
        </section>
      </main>
    </>
  );
}
