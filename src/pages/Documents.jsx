import { useEffect, useRef, useState } from "react";
import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { useAuth } from "../components/AuthProvider.jsx";
import Button from "../components/Button.jsx";
import Navbar from "../components/Navbar.jsx";
import {
  deleteDocument,
  getDocumentDownloadUrl,
  listDocuments,
  reprocessDocument,
} from "../lib/documentsApi.js";

const READY_STATUSES = new Set(["processed", "processed_with_warning"]);
const ACTIVE_STATUSES = new Set([
  "checking_text",
  "ocr_required",
  "running_ocr",
  "extracting",
  "chunking",
  "embedding",
]);

export default function Documents() {
  const { isSignedIn, loading: authLoading } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [status, setStatus] = useState("loading");
  const [message, setMessage] = useState("");
  const [actionError, setActionError] = useState("");
  const [deletingIds, setDeletingIds] = useState(() => new Set());
  const [downloadingId, setDownloadingId] = useState(null);
  const [reprocessingIds, setReprocessingIds] = useState(() => new Set());
  const documentsRequestedRef = useRef(false);

  useEffect(() => {
    if (authLoading) {
      setStatus("loading");
      setMessage("Loading documents...");
      return undefined;
    }

    if (!isSignedIn) {
      documentsRequestedRef.current = false;
      setStatus("error");
      setMessage("Please sign in to view documents.");
      return undefined;
    }

    if (documentsRequestedRef.current) return undefined;
    documentsRequestedRef.current = true;

    setStatus("loading");
    setMessage("Loading documents...");
    listDocuments()
      .then((items) => {
        setDocuments(items);
        setStatus("ready");
      })
      .catch((error) => {
        setStatus("error");
        setMessage(error.message);
      });
    return undefined;
  }, [authLoading, isSignedIn]);

  async function handleDelete(document) {
    const documentId = document.id;
    const confirmed = window.confirm("Delete this document forever?");
    if (!confirmed) return;

    try {
      setDeletingIds((current) => new Set(current).add(documentId));
      setActionError("");
      await deleteDocument(documentId);
      setDocuments((current) => current.filter((item) => item.id !== documentId));
      setStatus("ready");
    } catch (error) {
      setActionError(error.message);
    } finally {
      setDeletingIds((current) => {
        const next = new Set(current);
        next.delete(documentId);
        return next;
      });
    }
  }

  async function handleDownload(document) {
    const documentId = document.id;
    try {
      setDownloadingId(documentId);
      setActionError("");
      const { downloadUrl } = await getDocumentDownloadUrl(documentId);
      window.open(downloadUrl, "_blank", "noopener,noreferrer");
    } catch (error) {
      setActionError(error.message);
    } finally {
      setDownloadingId(null);
    }
  }

  async function handleReprocess(document) {
    try {
      setActionError("");
      setReprocessingIds((current) => new Set(current).add(document.id));
      setDocuments((current) => current.map((item) => (
        item.id === document.id ? { ...item, status: "checking_text", processing_error: null } : item
      )));
      const updatedDocument = await reprocessDocument(document.id);
      setDocuments((current) => current.map((item) => (
        item.id === document.id ? updatedDocument : item
      )));
    } catch (error) {
      setActionError(error.message);
      setDocuments((current) => current.map((item) => (
        item.id === document.id ? document : item
      )));
    } finally {
      setReprocessingIds((current) => {
        const next = new Set(current);
        next.delete(document.id);
        return next;
      });
    }
  }

  function documentStatusLabel(statusValue) {
    if (statusValue === "processed") return "Document Processed";
    if (statusValue === "processed_with_warning") return "Ready - review suggested";
    if (statusValue === "uploaded") return "Uploaded";
    if (statusValue === "checking_text") return "Checking document text";
    if (statusValue === "ocr_required") return "Scanned pages detected";
    if (statusValue === "running_ocr") return "Reading scanned pages";
    if (statusValue === "extracting") return "Building searchable text";
    if (statusValue === "chunking") return "Building searchable text";
    if (statusValue === "embedding") return "Creating document intelligence";
    if (["extraction_failed", "failed"].includes(statusValue)) return "Processing failed";
    if (statusValue === "needs_review") return "Needs review";
    return "Processing...";
  }

  return (
    <>
      <Navbar />
      <main className="documents-page">
        <section className="documents-shell">
          <div className="documents-heading">
            <div>
              <p className="eyebrow">Document workspace</p>
              <h1>Uploaded intelligence.</h1>
            </div>
            <Button to="/upload-document">Upload Document</Button>
          </div>

          {status === "loading" && <p className="documents-message">Loading documents...</p>}
          {status === "error" && (
            <div className="documents-message error documents-error-state">
              <span>{message}</span>
              {!authLoading && !isSignedIn && (
                <Button className="mobile-only-auth-action" to="/sign-in" variant="secondary">
                  Sign In
                </Button>
              )}
            </div>
          )}
          {actionError && <p className="documents-message error">{actionError}</p>}
          {status === "ready" && documents.length === 0 && (
            <p className="documents-message">No documents yet. Upload your first contract.</p>
          )}

          <div className="documents-grid">
            {documents.map((document) => {
              const isProcessed = READY_STATUSES.has(document.status);
              const isProcessing = ACTIVE_STATUSES.has(document.status) || reprocessingIds.has(document.id);
              const needsReview = ["processed_with_warning", "needs_review", "failed", "extraction_failed"].includes(document.status);
              const reviewPages = document.low_confidence_pages || [];

              return (
                <article
                  className={`document-row${isProcessed ? " document-row-processed" : ""}`}
                  key={document.id}
                >
                  {isProcessed && (
                    <Link
                      className="document-row-link"
                      to={`/documents/${document.id}/workspace`}
                      aria-label={`Open ${document.title} in the AI workspace`}
                      onKeyDown={(event) => {
                        if (event.key !== " ") return;
                        event.preventDefault();
                        event.currentTarget.click();
                      }}
                    />
                  )}
                  <div className="document-identity">
                    {isProcessed ? (
                      <span className={`document-ready-label${document.status === "processed_with_warning" ? " has-warning" : ""}`}>
                        <i aria-hidden="true" /> {document.status === "processed_with_warning" ? "Ready / Review suggested" : "Processed / Ready"}
                      </span>
                    ) : (
                      <span>{documentStatusLabel(document.status)}</span>
                    )}
                    <h2>{document.title}</h2>
                    <p>{document.file_name}</p>
                    {document.processing_error && (
                      <p className="document-processing-note">{document.processing_error}</p>
                    )}
                    {document.status === "processed_with_warning" && (
                      <p className="document-processing-note">
                        Some scanned text may be incomplete. Review source page{reviewPages.length === 1 ? "" : "s"}
                        {reviewPages.length ? ` ${reviewPages.join(", ")}.` : "."}
                      </p>
                    )}
                  </div>
                  <div className="document-actions">
                    <div className="document-metadata">
                      <strong>{(document.file_size / (1024 * 1024)).toFixed(2)} MB</strong>
                      <span>{document.mime_type}</span>
                    </div>
                    <div className="document-action-buttons">
                      {isProcessed ? (
                        <div className="document-primary-block">
                          <span>Review clauses, risks, and summaries.</span>
                          <Link
                            className="document-workspace-action"
                            to={`/documents/${document.id}/workspace`}
                            onClick={(event) => event.stopPropagation()}
                            aria-label={`Open AI workspace for ${document.title}`}
                          >
                            <span>Open Workspace</span>
                            <ArrowRight aria-hidden="true" size={17} strokeWidth={1.8} />
                          </Link>
                        </div>
                      ) : (
                        <span className={`document-status-pill status-${document.status}`}>
                          {documentStatusLabel(document.status)}
                        </span>
                      )}
                      {document.mime_type === "application/pdf" && (
                        <button
                          className="document-action-button document-reprocess"
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            handleReprocess(document);
                          }}
                          disabled={isProcessing}
                          aria-label={`Retry text recognition for ${document.title}`}
                        >
                          {isProcessing ? "Processing..." : needsReview ? "Retry text recognition" : "Reprocess"}
                        </button>
                      )}
                      {["needs_review", "failed", "extraction_failed"].includes(document.status) && (
                        <Link
                          className="document-action-button document-replace-link"
                          to="/upload-document"
                          onClick={(event) => event.stopPropagation()}
                        >
                          Replace file
                        </Link>
                      )}
                      <button
                        className="document-action-button"
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          handleDownload(document);
                        }}
                        disabled={downloadingId === document.id}
                        aria-label={`Download ${document.title}`}
                      >
                        {downloadingId === document.id
                          ? "Opening..."
                          : document.status === "processed_with_warning"
                            ? "Review source PDF"
                            : "Download"}
                      </button>
                      <button
                        className="document-action-button document-delete"
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          handleDelete(document);
                        }}
                        disabled={deletingIds.has(document.id)}
                        aria-label={`Delete ${document.title}`}
                      >
                        {deletingIds.has(document.id) ? "Deleting..." : "Delete"}
                      </button>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      </main>
    </>
  );
}
