import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import Button from "../components/Button.jsx";
import Navbar from "../components/Navbar.jsx";
import { askDocumentQuestion, getDocumentDownloadUrl, listDocuments } from "../lib/documentsApi.js";

const WORKSPACE_TABS = [
  { id: "ask", label: "Chat", detail: "Chat with your legal document", enabled: true },
  { id: "summary", label: "Executive Summary", detail: "Generate a concise legal summary", enabled: false },
  { id: "clauses", label: "Clause Intelligence", detail: "Extract and explain key legal clauses", enabled: false },
  { id: "risks", label: "Risk Analysis", detail: "Identify potential legal risks and unusual terms", enabled: false },
  { id: "compare", label: "Compare", detail: "Compare documents", enabled: false },
];

function messageId() {
  return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function displayFileName(fileName = "") {
  const trimmed = fileName.trim();
  if (!trimmed) return "Document.pdf";

  const extensionMatch = trimmed.match(/(\.[A-Za-z0-9]+)$/);
  const extension = extensionMatch?.[1] || "";
  const baseName = extension ? trimmed.slice(0, -extension.length) : trimmed;
  const readableBase = baseName
    .replace(/^\d+[-_\s]*/, "")
    .replace(/[-_]+/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\s+/g, " ")
    .trim();

  return `${readableBase || baseName || "Document"}${extension}`;
}

export default function DocumentWorkspace() {
  const { documentId } = useParams();
  const [documents, setDocuments] = useState([]);
  const [status, setStatus] = useState("loading");
  const [message, setMessage] = useState("");
  const [activeTab, setActiveTab] = useState("ask");
  const [question, setQuestion] = useState("");
  const [chat, setChat] = useState([]);
  const [askStatus, setAskStatus] = useState("idle");
  const [askError, setAskError] = useState("");
  const [downloading, setDownloading] = useState(false);

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

  const document = useMemo(
    () => documents.find((item) => item.id === documentId),
    [documentId, documents],
  );

  const readableFileName = displayFileName(document?.file_name || document?.title);

  async function handleDownload() {
    if (!document || downloading) return;

    try {
      setDownloading(true);
      const { downloadUrl } = await getDocumentDownloadUrl(document.id);
      window.open(downloadUrl, "_blank", "noopener,noreferrer");
    } finally {
      setDownloading(false);
    }
  }

  async function handleAskSubmit(event) {
    event.preventDefault();
    const nextQuestion = question.trim();
    if (!nextQuestion || askStatus === "asking") return;

    const userMessage = {
      id: messageId(),
      role: "user",
      text: nextQuestion,
    };

    setChat((current) => [...current, userMessage]);
    setQuestion("");
    setAskError("");
    setAskStatus("asking");

    try {
      const result = await askDocumentQuestion(documentId, nextQuestion);
      setChat((current) => [
        ...current,
        {
          id: messageId(),
          role: "juris",
          text: result.answer,
          sources: result.sources || [],
        },
      ]);
      setAskStatus("idle");
    } catch (error) {
      setAskError(error.message || "Juris could not answer that question.");
      setAskStatus("idle");
    }
  }

  return (
    <>
      <Navbar />
      <main className="workspace-page">
        <section className="workspace-shell">
          <div className="workspace-heading">
            <div>
              <p className="workspace-kicker">Document AI Workspace</p>
              <div className="workspace-title-row">
                <h1>{document ? readableFileName : "Document workspace"}</h1>
                {document?.status === "processed" && <span className="processed-badge">Processed ✓</span>}
              </div>
              {document && <p className="workspace-original-name">Original file: {document.file_name}</p>}
            </div>
            <div className="workspace-actions">
              <Button to="/documents" variant="secondary">Back to Documents</Button>
              {document && (
                <button
                  className="workspace-download-button"
                  type="button"
                  onClick={handleDownload}
                  disabled={downloading}
                  aria-label={`Download ${readableFileName}`}
                  title="Download PDF"
                >
                  <span aria-hidden="true">↓</span>
                  {downloading ? "Opening" : "PDF"}
                </button>
              )}
            </div>
          </div>

          {status === "loading" && <p className="documents-message">Loading workspace...</p>}
          {status === "error" && <p className="documents-message error">{message}</p>}
          {status === "ready" && !document && (
            <p className="documents-message error">Document not found.</p>
          )}

          {document && (
            <div className="workspace-grid">
              <aside className="workspace-tabs" aria-label="Document AI features">
                <div className="workspace-sidebar-title">AI Workspace</div>
                {WORKSPACE_TABS.map((tab) => (
                  <button
                    className={`workspace-tab ${activeTab === tab.id ? "active" : ""} ${tab.enabled ? "" : "disabled"}`}
                    type="button"
                    key={tab.id}
                    onClick={() => {
                      if (tab.enabled) setActiveTab(tab.id);
                    }}
                    aria-disabled={!tab.enabled}
                  >
                    <i aria-hidden="true">{activeTab === tab.id ? "●" : "○"}</i>
                    <span>{tab.label}</span>
                    <p>{tab.detail}</p>
                  </button>
                ))}
              </aside>

              <section className="workspace-panel">
                {activeTab === "ask" ? (
                  <AskChat
                    askError={askError}
                    askStatus={askStatus}
                    chat={chat}
                    document={document}
                    handleAskSubmit={handleAskSubmit}
                    question={question}
                    setQuestion={setQuestion}
                  />
                ) : (
                  <DisabledTool tab={WORKSPACE_TABS.find((tab) => tab.id === activeTab)} />
                )}
              </section>
            </div>
          )}
        </section>
      </main>
    </>
  );
}

function AskChat({ askError, askStatus, chat, document, handleAskSubmit, question, setQuestion }) {
  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  return (
    <div className="ask-workspace">
      <div className="ask-workspace-header">
        <div>
          <h2>Chat with your legal document</h2>
          <p>Ask questions about clauses, payments, obligations and legal terms.</p>
        </div>
        <span className={`document-status-pill status-${document.status}`}>
          {document.status === "processed" ? "Processed ✓" : document.status}
        </span>
      </div>

      <div className="chat-thread" aria-live="polite">
        {chat.length === 0 && (
          <div className="chat-empty">
            <span>Juris.</span>
            <p>Chat with your legal document.</p>
          </div>
        )}

        {chat.map((message) => (
          <article className={`chat-message ${message.role}`} key={message.id}>
            <span>{message.role === "user" ? "You" : "Juris"}</span>
            <div className="chat-message-text">{message.text}</div>
            {message.role === "juris" && (
              <details className="chat-sources">
                <summary>Sources ({message.sources?.length || 0})</summary>
                {message.sources?.length > 0 ? (
                  message.sources.map((source) => (
                    <details className="chat-source" key={`${message.id}-${source.chunk_index}`}>
                      <summary>Chunk {source.chunk_index}</summary>
                      <p>{source.preview}</p>
                    </details>
                  ))
                ) : (
                  <p>No sources returned.</p>
                )}
              </details>
            )}
          </article>
        ))}

        {askStatus === "asking" && (
          <article className="chat-message juris loading">
            <span>Juris</span>
            <div className="chat-message-text">Reading the relevant chunks...</div>
          </article>
        )}
      </div>

      {askError && <p className="ask-message error">{askError}</p>}

      <form className="workspace-ask-form" onSubmit={handleAskSubmit}>
        <textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything about this legal document..."
          rows={1}
        />
        <Button type="submit" disabled={askStatus === "asking" || !question.trim()}>
          {askStatus === "asking" ? "..." : "Send"}
        </Button>
      </form>
    </div>
  );
}

function DisabledTool({ tab }) {
  return (
    <div className="workspace-disabled-tool">
      <span>{tab?.label}</span>
      <h2>{tab?.detail}</h2>
      <p>Reserved for advanced document intelligence in this workspace.</p>
    </div>
  );
}
