import { useEffect, useState } from "react";
import Button from "../components/Button.jsx";
import Navbar from "../components/Navbar.jsx";
import {
  deleteDocument,
  getDocumentDownloadUrl,
  listDocuments,
} from "../lib/documentsApi.js";

export default function Documents() {
  const [documents, setDocuments] = useState([]);
  const [status, setStatus] = useState("loading");
  const [message, setMessage] = useState("");
  const [actionError, setActionError] = useState("");
  const [deletingIds, setDeletingIds] = useState(() => new Set());
  const [downloadingId, setDownloadingId] = useState(null);

  useEffect(() => {
    let active = true;
    listDocuments()
      .then((items) => {
        if (!active) return;
        setDocuments(items);
        setStatus("ready");
      })
      .catch((error) => {
        if (!active) return;
        setStatus("error");
        setMessage(error.message);
      });
    return () => {
      active = false;
    };
  }, []);

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
          {status === "error" && <p className="documents-message error">{message}</p>}
          {actionError && <p className="documents-message error">{actionError}</p>}
          {status === "ready" && documents.length === 0 && (
            <p className="documents-message">No documents yet. Upload your first contract.</p>
          )}

          <div className="documents-grid">
            {documents.map((document) => (
              <article className="document-row" key={document.id}>
                <div>
                  <span>{document.status}</span>
                  <h2>{document.title}</h2>
                  <p>{document.file_name}</p>
                </div>
                <div className="document-actions">
                  <div>
                    <strong>{(document.file_size / (1024 * 1024)).toFixed(2)} MB</strong>
                    <span>{document.mime_type}</span>
                  </div>
                  <div className="document-action-buttons">
                    {document.status === "processed" ? (
                      <Button
                        to={`/documents/${document.id}/workspace`}
                        variant="secondary"
                        className="document-processed-button"
                        aria-label={`Open AI workspace for ${document.title}`}
                      >
                        Document Processed
                      </Button>
                    ) : (
                      <span className={`document-status-pill status-${document.status}`}>
                        {documentStatusLabel(document.status)}
                      </span>
                    )}
                    <button
                      className="document-action-button"
                      type="button"
                      onClick={() => handleDownload(document)}
                      disabled={downloadingId === document.id}
                      aria-label={`Download ${document.title}`}
                    >
                      {downloadingId === document.id ? "Opening..." : "Download"}
                    </button>
                    <button
                      className="document-action-button document-delete"
                      type="button"
                      onClick={() => handleDelete(document)}
                      disabled={deletingIds.has(document.id)}
                      aria-label={`Delete ${document.title}`}
                    >
                      {deletingIds.has(document.id) ? "Deleting..." : "Delete"}
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>
      </main>
    </>
  );
}
