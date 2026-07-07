import { useEffect, useState } from "react";
import Button from "../components/Button.jsx";
import Navbar from "../components/Navbar.jsx";
import { deleteDocument, listDocuments } from "../lib/documentsApi.js";

export default function Documents() {
  const [documents, setDocuments] = useState([]);
  const [status, setStatus] = useState("loading");
  const [message, setMessage] = useState("");
  const [deletingId, setDeletingId] = useState(null);

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
    const confirmed = window.confirm("Delete this document forever?");
    if (!confirmed) return;

    try {
      setDeletingId(document.id);
      setMessage("");
      await deleteDocument(document.id);
      setDocuments((current) => current.filter((item) => item.id !== document.id));
      setStatus("ready");
    } catch (error) {
      setStatus("error");
      setMessage(error.message);
    } finally {
      setDeletingId(null);
    }
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
                  <button
                    className="document-delete"
                    type="button"
                    onClick={() => handleDelete(document)}
                    disabled={deletingId === document.id}
                    aria-label={`Delete ${document.title}`}
                  >
                    {deletingId === document.id ? "Deleting..." : "Delete"}
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      </main>
    </>
  );
}
