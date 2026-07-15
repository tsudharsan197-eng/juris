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
} from "../lib/documentsApi.js";

export default function Documents() {
  const { isSignedIn, loading: authLoading } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [status, setStatus] = useState("loading");
  const [message, setMessage] = useState("");
  const [actionError, setActionError] = useState("");
  const [deletingIds, setDeletingIds] = useState(() => new Set());
  const [downloadingId, setDownloadingId] = useState(null);
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

  function documentStatusLabel(statusValue) {
    if (statusValue === "processed") return "Document Processed";
    if (statusValue === "uploaded") return "Uploaded";
    if (statusValue === "extraction_failed") return "Processing failed";
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
              const isProcessed = document.status === "processed";

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
                      <span className="document-ready-label"><i aria-hidden="true" /> Processed / Ready</span>
                    ) : (
                      <span>{document.status}</span>
                    )}
                    <h2>{document.title}</h2>
                    <p>{document.file_name}</p>
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
                        {downloadingId === document.id ? "Opening..." : "Download"}
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
