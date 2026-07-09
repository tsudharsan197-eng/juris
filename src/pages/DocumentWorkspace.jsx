import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useAuth } from "../components/AuthProvider.jsx";
import Button from "../components/Button.jsx";
import Navbar from "../components/Navbar.jsx";
import {
  askDocumentQuestion,
  compareDocuments,
  getDocumentClauses,
  getDocumentDownloadUrl,
  getDocumentIntelligence,
  getDocumentRiskAnalysis,
  getDocumentSummary,
  listDocuments,
} from "../lib/documentsApi.js";

const WORKSPACE_TABS = [
  { id: "ask", label: "Chat", detail: "Chat with your legal document", enabled: true },
  { id: "intelligence", label: "Document Intelligence", detail: "Flagship legal intelligence dashboard", enabled: true },
  { id: "summary", label: "Executive Summary", detail: "Generate a concise legal summary", enabled: true },
  { id: "clauses", label: "Clause Intelligence", detail: "Extract and explain key legal clauses", enabled: true },
  { id: "risks", label: "Risk Analysis", detail: "Identify potential legal risks and unusual terms", enabled: true },
  { id: "compare", label: "Compare", detail: "Compare documents", enabled: true },
];

const AI_LOADING_DELAY_MS = 180;

function startDeferredLoading(setStatus) {
  setStatus("pending");
  return globalThis.setTimeout?.(() => {
    setStatus((current) => (current === "pending" ? "loading" : current));
  }, AI_LOADING_DELAY_MS);
}

function isAiLoading(status) {
  return status === "pending" || status === "loading";
}

function abortRequest(ref) {
  ref.current?.abort();
  ref.current = null;
}

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
  const { isSignedIn, loading: authLoading } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [status, setStatus] = useState("loading");
  const [message, setMessage] = useState("");
  const [activeTab, setActiveTab] = useState("ask");
  const [question, setQuestion] = useState("");
  const [chat, setChat] = useState([]);
  const [askStatus, setAskStatus] = useState("idle");
  const [askError, setAskError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [summary, setSummary] = useState("");
  const [summaryStatus, setSummaryStatus] = useState("idle");
  const [summaryError, setSummaryError] = useState("");
  const [intelligence, setIntelligence] = useState(null);
  const [intelligenceStatus, setIntelligenceStatus] = useState("idle");
  const [intelligenceError, setIntelligenceError] = useState("");
  const [clauses, setClauses] = useState(null);
  const [clausesStatus, setClausesStatus] = useState("idle");
  const [clausesError, setClausesError] = useState("");
  const [riskAnalysis, setRiskAnalysis] = useState(null);
  const [riskStatus, setRiskStatus] = useState("idle");
  const [riskError, setRiskError] = useState("");
  const [compareResult, setCompareResult] = useState(null);
  const [compareStatus, setCompareStatus] = useState("idle");
  const [compareError, setCompareError] = useState("");
  const [compareTargetId, setCompareTargetId] = useState("");
  const summaryRequestRef = useRef(null);
  const intelligenceRequestRef = useRef(null);
  const clausesRequestRef = useRef(null);
  const riskRequestRef = useRef(null);
  const compareRequestRef = useRef(null);
  const documentsRequestedRef = useRef(false);

  useEffect(() => {
    if (authLoading) {
      setStatus("loading");
      setMessage("Loading AI workspace...");
      return undefined;
    }

    if (!isSignedIn) {
      documentsRequestedRef.current = false;
      setStatus("error");
      setMessage("Please sign in to open the AI workspace.");
      return undefined;
    }

    if (documentsRequestedRef.current) return undefined;
    documentsRequestedRef.current = true;

    setStatus("loading");
    setMessage("Loading AI workspace...");
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

  const document = useMemo(
    () => documents.find((item) => item.id === documentId),
    [documentId, documents],
  );

  const readableFileName = displayFileName(document?.file_name || document?.title);

  useEffect(() => {
    setSummary("");
    setSummaryStatus("idle");
    setSummaryError("");
    setIntelligence(null);
    setIntelligenceStatus("idle");
    setIntelligenceError("");
    setClauses(null);
    setClausesStatus("idle");
    setClausesError("");
    setRiskAnalysis(null);
    setRiskStatus("idle");
    setRiskError("");
    setCompareResult(null);
    setCompareStatus("idle");
    setCompareError("");
    setCompareTargetId("");
    abortRequest(summaryRequestRef);
    abortRequest(intelligenceRequestRef);
    abortRequest(clausesRequestRef);
    abortRequest(riskRequestRef);
    abortRequest(compareRequestRef);
  }, [documentId]);

  useEffect(() => () => {
    abortRequest(summaryRequestRef);
    abortRequest(intelligenceRequestRef);
    abortRequest(clausesRequestRef);
    abortRequest(riskRequestRef);
    abortRequest(compareRequestRef);
  }, []);

  useEffect(() => {
    setCompareResult(null);
    setCompareStatus("idle");
    setCompareError("");
    abortRequest(compareRequestRef);
  }, [compareTargetId]);

  async function loadSummary() {
    if (!document || summary || isAiLoading(summaryStatus) || summaryStatus === "ready" || summaryRequestRef.current) return;
    const controller = new AbortController();
    summaryRequestRef.current = controller;
    const loadingTimer = startDeferredLoading(setSummaryStatus);
    setSummaryError("");

    try {
      const markdown = await getDocumentSummary(document.id, { signal: controller.signal });
      console.info("[Juris AI summary success]", { documentId: document.id, markdownLength: markdown.length });
      setSummary(markdown || "");
      setSummaryStatus("ready");
    } catch (error) {
      if (error.name === "AbortError") {
        console.info("[Juris AI summary aborted]", { documentId: document.id });
        setSummaryStatus("idle");
        return;
      }
      console.error("[Juris AI summary failed]", error);
      setSummaryError(error.message || "Juris could not generate the executive summary.");
      setSummaryStatus("error");
    } finally {
      clearTimeout(loadingTimer);
      if (summaryRequestRef.current === controller) summaryRequestRef.current = null;
    }
  }

  async function loadIntelligence() {
    if (!document || intelligence || isAiLoading(intelligenceStatus) || intelligenceStatus === "ready" || intelligenceRequestRef.current) return;
    const controller = new AbortController();
    intelligenceRequestRef.current = controller;
    const loadingTimer = startDeferredLoading(setIntelligenceStatus);
    setIntelligenceError("");

    try {
      const payload = await getDocumentIntelligence(document.id, { signal: controller.signal });
      console.info("[Juris AI intelligence success]", { documentId: document.id, payload });
      setIntelligence(payload);
      setIntelligenceStatus("ready");
    } catch (error) {
      if (error.name === "AbortError") {
        console.info("[Juris AI intelligence aborted]", { documentId: document.id });
        setIntelligenceStatus("idle");
        return;
      }
      console.error("[Juris AI intelligence failed]", error);
      setIntelligenceError(error.message || "Juris could not generate document intelligence.");
      setIntelligenceStatus("error");
    } finally {
      clearTimeout(loadingTimer);
      if (intelligenceRequestRef.current === controller) intelligenceRequestRef.current = null;
    }
  }

  async function loadClauses() {
    if (!document || clauses || isAiLoading(clausesStatus) || clausesStatus === "ready" || clausesRequestRef.current) return;
    const controller = new AbortController();
    clausesRequestRef.current = controller;
    const loadingTimer = startDeferredLoading(setClausesStatus);
    setClausesError("");

    try {
      const payload = await getDocumentClauses(document.id, { signal: controller.signal });
      console.info("[Juris AI clauses success]", { documentId: document.id, payload });
      setClauses(payload);
      setClausesStatus("ready");
    } catch (error) {
      if (error.name === "AbortError") {
        console.info("[Juris AI clauses aborted]", { documentId: document.id });
        setClausesStatus("idle");
        return;
      }
      console.error("[Juris AI clauses failed]", error);
      setClausesError(error.message || "Juris could not generate clause intelligence.");
      setClausesStatus("error");
    } finally {
      clearTimeout(loadingTimer);
      if (clausesRequestRef.current === controller) clausesRequestRef.current = null;
    }
  }

  async function loadRiskAnalysis() {
    if (!document || riskAnalysis || isAiLoading(riskStatus) || riskStatus === "ready" || riskRequestRef.current) return;
    const controller = new AbortController();
    riskRequestRef.current = controller;
    const loadingTimer = startDeferredLoading(setRiskStatus);
    setRiskError("");

    try {
      const payload = await getDocumentRiskAnalysis(document.id, { signal: controller.signal });
      console.info("[Juris AI risk analysis success]", { documentId: document.id, payload });
      setRiskAnalysis(payload);
      setRiskStatus("ready");
    } catch (error) {
      if (error.name === "AbortError") {
        console.info("[Juris AI risk analysis aborted]", { documentId: document.id });
        setRiskStatus("idle");
        return;
      }
      console.error("[Juris AI risk analysis failed]", error);
      setRiskError(error.message || "Juris could not generate risk analysis.");
      setRiskStatus("error");
    } finally {
      clearTimeout(loadingTimer);
      if (riskRequestRef.current === controller) riskRequestRef.current = null;
    }
  }

  async function handleCompareDocuments(secondDocumentId) {
    if (!document || !secondDocumentId || isAiLoading(compareStatus) || (compareStatus === "ready" && compareResult)) return;

    const controller = new AbortController();
    compareRequestRef.current?.abort();
    compareRequestRef.current = controller;
    const loadingTimer = startDeferredLoading(setCompareStatus);
    setCompareError("");
    setCompareResult(null);

    try {
      const payload = await compareDocuments(document.id, secondDocumentId, { signal: controller.signal });
      console.info("[Juris AI compare success]", { documentId: document.id, secondDocumentId, payload });
      setCompareResult(payload);
      setCompareStatus("ready");
    } catch (error) {
      if (error.name === "AbortError") {
        console.info("[Juris AI compare aborted]", { documentId: document.id, secondDocumentId });
        setCompareStatus("idle");
        return;
      }
      console.error("[Juris AI compare failed]", error);
      setCompareError(error.message || "Juris could not compare these documents.");
      setCompareStatus("error");
    } finally {
      clearTimeout(loadingTimer);
      if (compareRequestRef.current === controller) compareRequestRef.current = null;
    }
  }

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

  async function askQuestion(nextQuestionValue) {
    const nextQuestion = String(nextQuestionValue || "").trim();
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

  async function handleAskSubmit(event) {
    event.preventDefault();
    await askQuestion(question);
  }

  function handleRecommendedQuestion(nextQuestion) {
    setActiveTab("ask");
    askQuestion(nextQuestion);
  }

  function handleTabSelect(tab) {
    if (!tab.enabled) return;
    setActiveTab(tab.id);
    if (tab.id === "summary") void loadSummary();
    if (tab.id === "intelligence") void loadIntelligence();
    if (tab.id === "clauses") void loadClauses();
    if (tab.id === "risks") void loadRiskAnalysis();
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

          {status === "loading" && <p className="documents-message">{message || "Loading AI workspace..."}</p>}
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
                    onClick={() => handleTabSelect(tab)}
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
                ) : activeTab === "summary" ? (
                  <ExecutiveSummaryPanel
                    summary={summary}
                    summaryError={summaryError}
                    summaryStatus={summaryStatus}
                  />
                ) : activeTab === "intelligence" ? (
                  <DocumentIntelligencePanel
                    askStatus={askStatus}
                    intelligence={intelligence}
                    intelligenceError={intelligenceError}
                    intelligenceStatus={intelligenceStatus}
                    onQuestionClick={handleRecommendedQuestion}
                  />
                ) : activeTab === "clauses" ? (
                  <ClauseIntelligencePanel
                    clauses={clauses}
                    clausesError={clausesError}
                    clausesStatus={clausesStatus}
                  />
                ) : activeTab === "risks" ? (
                  <RiskAnalysisPanel
                    riskAnalysis={riskAnalysis}
                    riskError={riskError}
                    riskStatus={riskStatus}
                  />
                ) : activeTab === "compare" ? (
                  <CompareDocumentsPanel
                    compareError={compareError}
                    compareResult={compareResult}
                    compareStatus={compareStatus}
                    compareTargetId={compareTargetId}
                    currentDocument={document}
                    documents={documents}
                    onCompare={handleCompareDocuments}
                    setCompareTargetId={setCompareTargetId}
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

function ExecutiveSummaryPanel({ summary, summaryError, summaryStatus }) {
  return (
    <div className="summary-workspace">
      <div className="summary-workspace-header">
        <span>Executive Summary</span>
        <h2>Document-type aware legal summary</h2>
        <p>Juris identifies the document type, then summarizes parties, key terms, obligations, rights, risks, and missing information.</p>
      </div>

      {isAiLoading(summaryStatus) && (
        <AiLoadingPanel
          title="Generating executive summary..."
          subtitle="Reading document clauses, parties, obligations, and risks."
          items={["Document Type", "Parties Involved", "Key Terms", "Risk Notes"]}
        />
      )}

      {summaryStatus === "error" && <p className="ask-message error">{summaryError}</p>}

      {summaryStatus === "ready" && summary && (
        <div className="summary-markdown">
          <MarkdownView markdown={summary} />
        </div>
      )}
    </div>
  );
}

function DocumentIntelligencePanel({
  askStatus,
  intelligence,
  intelligenceError,
  intelligenceStatus,
  onQuestionClick,
}) {
  const isLoading = isAiLoading(intelligenceStatus);

  return (
    <div className="intelligence-workspace">
      <div className="intelligence-header">
        <span>Document Intelligence</span>
        <h2>What should you care about?</h2>
        <p>Juris identifies the document type first, then turns the file into a structured legal intelligence dashboard.</p>
      </div>

      {isLoading && (
        <AiLoadingPanel
          title="Building document intelligence..."
          subtitle="Extracting key terms, timelines, financial terms, obligations, risks, and missing information."
          items={[
            "Executive Snapshot",
            "Plain-English Summary",
            "Key Information",
            "Timeline",
            "Financial Summary",
            "Risk Highlights",
          ]}
          variant="intelligence"
        />
      )}

      {intelligenceStatus === "error" && <p className="ask-message error">{intelligenceError}</p>}

      {intelligenceStatus === "ready" && intelligence && (
        <IntelligenceDashboard
          askStatus={askStatus}
          data={intelligence}
          onQuestionClick={onQuestionClick}
        />
      )}
    </div>
  );
}

function ClauseIntelligencePanel({ clauses, clausesError, clausesStatus }) {
  const isLoading = isAiLoading(clausesStatus);

  return (
    <div className="clauses-workspace">
      <div className="clauses-header">
        <span>Clause Intelligence</span>
        <h2>Important clauses, explained simply</h2>
        <p>Juris identifies the document type, extracts supported clauses, and explains obligations, rights, restrictions, deadlines, and financial terms.</p>
      </div>

      {isLoading && (
        <AiLoadingPanel
          title="Extracting clause intelligence..."
          subtitle="Identifying key clauses, obligations, rights, restrictions, dates, financial terms, and risk signals."
          items={["Clause Titles", "Risk Levels", "Obligations", "Rights", "Deadlines", "Financial Terms"]}
          variant="clauses"
        />
      )}

      {clausesStatus === "error" && <p className="ask-message error">{clausesError}</p>}

      {clausesStatus === "ready" && clauses && (
        <ClauseDashboard data={clauses} />
      )}
    </div>
  );
}

function RiskAnalysisPanel({ riskAnalysis, riskError, riskStatus }) {
  const isLoading = isAiLoading(riskStatus);

  return (
    <div className="risk-workspace">
      <div className="risk-header">
        <span>Risk Analysis</span>
        <h2>Legal risk, translated into action</h2>
        <p>Juris identifies the document type first, then surfaces supported legal, financial, operational, and compliance risks in plain English.</p>
      </div>

      {isLoading && (
        <AiLoadingPanel
          title="Analyzing document risks..."
          subtitle="Reviewing legal impact, financial exposure, operational burden, missing protections, unusual terms, and compliance signals."
          items={["Overall Risk", "Legal Risks", "Financial Risks", "Missing Protections", "Unusual Terms", "Recommendations"]}
          variant="risks"
        />
      )}

      {riskStatus === "error" && <p className="ask-message error">{riskError}</p>}

      {riskStatus === "ready" && riskAnalysis && (
        <RiskDashboard data={riskAnalysis} />
      )}
    </div>
  );
}

function CompareDocumentsPanel({
  compareError,
  compareResult,
  compareStatus,
  compareTargetId,
  currentDocument,
  documents,
  onCompare,
  setCompareTargetId,
}) {
  const candidates = documents.filter((item) => item.id !== currentDocument.id && item.status === "processed");
  const selectedDocument = candidates.find((item) => item.id === compareTargetId);
  const isLoading = isAiLoading(compareStatus);
  const isSubmitting = isAiLoading(compareStatus);

  function handleSubmit(event) {
    event.preventDefault();
    onCompare(compareTargetId);
  }

  return (
    <div className="compare-workspace">
      <div className="compare-header">
        <span>Compare Documents</span>
        <h2>Understand what changed</h2>
        <p>Select another processed document and Juris will compare meaningful legal, financial, obligation, deadline, risk, and clause differences.</p>
      </div>

      <form className="compare-picker-card" onSubmit={handleSubmit}>
        <div className="compare-document-mini">
          <span>Current Document</span>
          <strong>{displayFileName(currentDocument.file_name || currentDocument.title)}</strong>
          <p>Document A</p>
        </div>

        <div className="compare-switch" aria-hidden="true">↔</div>

        <label className="compare-select-wrap">
          <span>Compare With</span>
          <select
            disabled={!candidates.length || isSubmitting}
            onChange={(event) => setCompareTargetId(event.target.value)}
            value={compareTargetId}
          >
            <option value="">Select a processed document</option>
            {candidates.map((item) => (
              <option key={item.id} value={item.id}>
                {displayFileName(item.file_name || item.title)}
              </option>
            ))}
          </select>
          <p>{candidates.length ? "Only processed documents are available for comparison." : "Upload and process another document to compare."}</p>
        </label>

        <Button type="submit" disabled={!compareTargetId || isSubmitting || !candidates.length}>
          {isSubmitting ? "Comparing..." : "Compare"}
        </Button>
      </form>

      {selectedDocument && compareStatus === "idle" && (
        <p className="compare-hint">Ready to compare with {displayFileName(selectedDocument.file_name || selectedDocument.title)}.</p>
      )}

      {isLoading && (
        <AiLoadingPanel
          title="Comparing documents..."
          subtitle="Checking document types, clause changes, payment terms, obligations, deadlines, and risk movement."
          items={["Document Types", "Clause Changes", "Financial Terms", "Obligations", "Deadlines", "Risk Changes"]}
          variant="compare"
        />
      )}

      {compareStatus === "error" && <p className="ask-message error">{compareError}</p>}

      {compareStatus === "ready" && compareResult && (
        <CompareDashboard data={compareResult} />
      )}
    </div>
  );
}

function AiLoadingPanel({ items = [], subtitle, title, variant = "summary" }) {
  return (
    <div className={`ai-loading-panel ${variant}`} role="status" aria-live="polite">
      <div className="ai-loading-copy">
        <span>Juris AI</span>
        <h3>{title}</h3>
        <p>{subtitle}</p>
      </div>

      <div className="ai-loading-track" aria-hidden="true">
        <span />
      </div>

      <div className="ai-loading-grid" aria-hidden="true">
        {items.map((item) => (
          <div className="ai-loading-card" key={item}>
            <div className="ai-loading-card-top">
              <i />
              <b>{item}</b>
            </div>
            <em />
            <em />
            <em className="short" />
          </div>
        ))}
      </div>
    </div>
  );
}

function ClauseDashboard({ data }) {
  const clauseItems = Array.isArray(data?.clauses) ? data.clauses : [];

  return (
    <div className="clause-dashboard">
      <section className="clause-document-card">
        <span>Document Type</span>
        <strong>{displayText(data?.documentType)}</strong>
        <p>{clauseItems.length ? `${clauseItems.length} supported clauses extracted from this document.` : "No supported clauses were extracted."}</p>
      </section>

      {clauseItems.length > 0 ? (
        <div className="clause-card-list">
          {clauseItems.map((clause, index) => (
            <ClauseCard clause={clause} index={index} key={`${displayText(clause.title)}-${displayText(clause.sourceReference)}-${index}`} />
          ))}
        </div>
      ) : (
        <section className="clause-empty-state">
          <span>Clause Intelligence</span>
          <h3>No clauses found</h3>
          <p>Juris could not identify supported clauses in the processed document chunks.</p>
        </section>
      )}
    </div>
  );
}

function ClauseCard({ clause, index }) {
  const riskLevel = displayText(clause.riskLevel);
  const riskClass = normalizedRiskClass(riskLevel);
  const importantTerms = listItems(clause.importantTerms);
  const obligations = listItems(clause.obligations);
  const rights = listItems(clause.rights);
  const restrictions = listItems(clause.restrictions);
  const deadlines = listItems(clause.deadlines);
  const financialTerms = listItems(clause.financialTerms);

  return (
    <article className="clause-intel-card">
      <div className="clause-card-top">
        <div>
          <span>Clause {String(index + 1).padStart(2, "0")} / {displayText(clause.category)}</span>
          <h3>{displayText(clause.title)}</h3>
        </div>
        <span className={`clause-risk risk-${riskClass}`}>{riskLevel}</span>
      </div>

      <div className="clause-card-body">
        <div>
          <p className="clause-field-label">Plain English</p>
          <p className="clause-plain-text">{displayText(clause.plainEnglish)}</p>
        </div>
        <div className="clause-why-block">
          <p className="clause-field-label">Why It Matters</p>
          <p>{displayText(clause.whyItMatters)}</p>
        </div>
      </div>

      <div className="clause-meta-strip">
        <span>Source: {displayText(clause.sourceReference)}</span>
        <span>Confidence: {formatConfidencePercentage(clause.confidence)}</span>
      </div>

      <div className="clause-detail-grid">
        <ClauseDetailSection title="Important Terms" count={importantTerms.length}>
          <TagList emptyText="Not applicable." items={importantTerms} />
        </ClauseDetailSection>
        <ClauseDetailSection title="Obligations" count={obligations.length}>
          <PartyActionList actionKey="obligation" emptyText="No obligations identified." items={obligations} />
        </ClauseDetailSection>
        <ClauseDetailSection title="Rights" count={rights.length}>
          <PartyActionList actionKey="right" emptyText="No rights identified." items={rights} />
        </ClauseDetailSection>
        <ClauseDetailSection title="Restrictions" count={restrictions.length}>
          <InsightList emptyText="No restrictions identified." items={restrictions} />
        </ClauseDetailSection>
        <ClauseDetailSection title="Deadlines" count={deadlines.length}>
          <InsightList emptyText="No deadlines identified." items={deadlines} />
        </ClauseDetailSection>
        <ClauseDetailSection title="Financial Terms" count={financialTerms.length}>
          <InsightList emptyText="No financial terms identified." items={financialTerms} />
        </ClauseDetailSection>
      </div>
    </article>
  );
}

function RiskDashboard({ data }) {
  const risks = Array.isArray(data?.risks) ? data.risks : [];
  const overallRisk = displayText(data?.overallRisk);
  const riskClass = normalizedRiskClass(overallRisk);
  const supportingSections = [
    ["Missing Protections", data?.missingProtections, "Protections that may need review."],
    ["Unusual Terms", data?.unusualTerms, "Unusual or one-sided terms surfaced by Juris."],
    ["Financial Risks", data?.financialRisks, "Money, fees, penalties, deposits, or payment exposure."],
    ["Legal Risks", data?.legalRisks, "Liability, termination, rights, disputes, or enforceability exposure."],
    ["Compliance Risks", data?.complianceRisks, "Privacy, regulatory, notice, consent, or policy obligations."],
  ];

  return (
    <div className="risk-dashboard">
      <section className="risk-overview-card">
        <div>
          <span>Document Type</span>
          <strong>{displayText(data?.documentType)}</strong>
        </div>
        <div className="risk-overview-main">
          <span className={`risk-overall-badge risk-${riskClass}`}>{overallRisk}</span>
          <p>{displayText(data?.summary)}</p>
        </div>
      </section>

      {risks.length > 0 ? (
        <div className="risk-card-list">
          {risks.map((risk, index) => (
            <RiskCard risk={risk} index={index} key={`${displayText(risk.title)}-${displayText(risk.sourceReference)}-${index}`} />
          ))}
        </div>
      ) : (
        <section className="risk-empty-state">
          <span>Risk Analysis</span>
          <h3>No supported risks detected</h3>
          <p>{displayText(data?.summary) || "Juris did not find document-supported risks in the processed chunks."}</p>
        </section>
      )}

      <div className="risk-support-grid">
        {supportingSections.map(([title, value, detail]) => (
          <RiskSupportCard
            detail={detail}
            items={listItems(value)}
            key={title}
            title={title}
          />
        ))}
      </div>
    </div>
  );
}

function RiskCard({ risk, index }) {
  const severity = displayText(risk.severity);
  const riskClass = normalizedRiskClass(severity);

  return (
    <article className="risk-item-card">
      <div className="risk-card-top">
        <div>
          <span>Risk {String(index + 1).padStart(2, "0")} / {displayText(risk.category)}</span>
          <h3>{displayText(risk.title)}</h3>
        </div>
        <span className={`risk-severity risk-${riskClass}`}>{severity}</span>
      </div>

      <div className="risk-explanation-grid">
        <div>
          <p className="risk-field-label">Plain English Explanation</p>
          <p>{displayText(risk.description)}</p>
        </div>
        <div>
          <p className="risk-field-label">Why It Matters</p>
          <p>{displayText(risk.whyItMatters)}</p>
        </div>
        <div className="risk-recommendation">
          <p className="risk-field-label">Recommendation</p>
          <p>{displayText(risk.recommendation)}</p>
        </div>
      </div>

      <div className="risk-meta-strip">
        <span>Affected party: {displayText(risk.affectedParty)}</span>
        <span>Source: {displayText(risk.sourceReference)}</span>
        <span>Confidence: {formatConfidencePercentage(risk.confidence)}</span>
      </div>
    </article>
  );
}

function RiskSupportCard({ detail, items, title }) {
  return (
    <section className="risk-support-card">
      <div>
        <span>{title}</span>
        <p>{detail}</p>
      </div>
      <InsightList emptyText="Not specified." items={items} tone={title.toLowerCase().includes("risk") ? "risk" : "neutral"} />
    </section>
  );
}

function CompareDashboard({ data }) {
  const differences = Array.isArray(data?.differences) ? data.differences : [];
  const areComparable = data?.areComparable === true;
  const supportingSections = [
    ["Financial Differences", data?.financialDifferences],
    ["Obligation Differences", data?.obligationDifferences],
    ["Deadline Differences", data?.deadlineDifferences],
    ["Risk Differences", data?.riskDifferences],
  ];
  const recommendedQuestions = listItems(data?.recommendedQuestions).slice(0, 5);

  return (
    <div className="compare-dashboard">
      <section className="compare-summary-card">
        <div className="compare-document-pair">
          <div>
            <span>Document A</span>
            <strong>{displayText(data?.documentA?.name)}</strong>
            <p>{displayText(data?.documentA?.documentType)}</p>
          </div>
          <i aria-hidden="true">vs</i>
          <div>
            <span>Document B</span>
            <strong>{displayText(data?.documentB?.name)}</strong>
            <p>{displayText(data?.documentB?.documentType)}</p>
          </div>
        </div>
        <div className="compare-summary-copy">
          <span className={`compare-status-badge ${areComparable ? "comparable" : "not-comparable"}`}>
            {areComparable ? "Comparable" : "Not Comparable"}
          </span>
          <p>{displayText(data?.summary)}</p>
        </div>
      </section>

      {!areComparable && (
        <section className="compare-friendly-card">
          <span>Comparison Note</span>
          <h3>These documents may not be the same type.</h3>
          <p>Juris can still show directly supported high-level differences, but the comparison may be less useful than comparing two documents with the same legal purpose.</p>
        </section>
      )}

      {differences.length > 0 ? (
        <div className="compare-difference-list">
          {differences.map((difference, index) => (
            <CompareDifferenceCard
              difference={difference}
              index={index}
              key={`${displayText(difference.title)}-${displayText(difference.sourceReference)}-${index}`}
            />
          ))}
        </div>
      ) : (
        <section className="compare-empty-state">
          <span>Differences</span>
          <h3>No supported differences detected</h3>
          <p>Juris did not find meaningful document-supported differences in the processed chunks.</p>
        </section>
      )}

      <div className="compare-support-grid">
        {supportingSections.map(([title, value]) => (
          <section className="compare-support-card" key={title}>
            <span>{title}</span>
            <InsightList emptyText="Not specified." items={listItems(value)} tone={title.toLowerCase().includes("risk") ? "risk" : "neutral"} />
          </section>
        ))}
      </div>

      <section className="compare-questions-card">
        <span>Recommended Questions</span>
        <div className="intel-question-chips">
          {recommendedQuestions.length ? (
            recommendedQuestions.map((question, index) => (
              <span className="compare-question-chip" key={`${displayText(question)}-${index}`}>
                {displayText(question)}
              </span>
            ))
          ) : (
            <p className="intel-empty">No recommended questions were generated.</p>
          )}
        </div>
      </section>
    </div>
  );
}

function CompareDifferenceCard({ difference, index }) {
  const type = displayText(difference.type);
  const typeClass = normalizedDifferenceClass(type);
  const riskChange = displayText(difference.riskChange);
  const riskClass = normalizedRiskChangeClass(riskChange);

  return (
    <article className="compare-difference-card">
      <div className="compare-difference-top">
        <div>
          <span>Difference {String(index + 1).padStart(2, "0")} / {displayText(difference.category)}</span>
          <h3>{displayText(difference.title)}</h3>
        </div>
        <div className="compare-badge-row">
          <span className={`compare-type-badge type-${typeClass}`}>{type}</span>
          <span className={`compare-risk-badge change-${riskClass}`}>{riskChange}</span>
        </div>
      </div>

      <div className="compare-document-values">
        <div>
          <span>Document A</span>
          <p>{displayText(difference.documentA)}</p>
        </div>
        <div>
          <span>Document B</span>
          <p>{displayText(difference.documentB)}</p>
        </div>
      </div>

      <div className="compare-impact-card">
        <p className="risk-field-label">Impact</p>
        <p>{displayText(difference.impact)}</p>
      </div>

      <div className="risk-meta-strip">
        <span>Affected party: {displayText(difference.affectedParty)}</span>
        <span>Source: {displayText(difference.sourceReference)}</span>
        <span>Confidence: {formatConfidencePercentage(difference.confidence)}</span>
      </div>
    </article>
  );
}

function ClauseDetailSection({ children, count, title }) {
  return (
    <details className="clause-detail-section">
      <summary>
        <span>{title}</span>
        <em>{count}</em>
      </summary>
      <div className="clause-detail-content">
        {children}
      </div>
    </details>
  );
}

function PartyActionList({ actionKey, emptyText, items }) {
  const normalizedItems = items
    .map((item) => {
      if (item && typeof item === "object" && !Array.isArray(item)) {
        return {
          party: displayText(item.party),
          action: displayText(item[actionKey]),
        };
      }
      return { party: "Not specified", action: displayText(item) };
    })
    .filter((item) => hasUsableValue(item.action) && !isNotSpecified(item.action));

  if (!normalizedItems.length) return <p className="intel-empty">{emptyText}</p>;

  return (
    <div className="clause-party-actions">
      {normalizedItems.map((item, index) => (
        <div className="clause-party-action" key={`${item.party}-${item.action}-${index}`}>
          <span>{item.party}</span>
          <p>{item.action}</p>
        </div>
      ))}
    </div>
  );
}

function IntelligenceDashboard({ askStatus, data, onQuestionClick }) {
  const snapshot = buildSnapshot(data);
  const keyInformation = objectEntries(data.keyInformation, { hideNotSpecified: true });
  const timeline = listItems(data.timeline);
  const financialSummary = objectEntries(data.financialSummary, { hideNotSpecified: true });
  const obligations = objectEntries(data.obligations);
  const keyClauses = listItems(data.keyClauses);
  const riskHighlights = listItems(data.riskHighlights);
  const missingInformation = listItems(data.missingInformation);
  const recommendedQuestions = listItems(data.recommendedQuestions).slice(0, 5);

  return (
    <div className="intelligence-dashboard">
      <IntelligenceCard className="intel-card-wide" icon="#" label="Executive Snapshot">
        <div className="intel-snapshot-grid">
          {snapshot.items.map((item) => (
            <div className="intel-metric" key={item.label}>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
      </IntelligenceCard>

      <IntelligenceCard className="intel-card-wide" icon="30" label="Plain-English Summary">
        <p className="intel-summary-text">{displayText(data.plainEnglishSummary)}</p>
      </IntelligenceCard>

      <IntelligenceCard icon="i" label="Key Information">
        <KeyValueGrid
          emptyText="Not specified."
          entries={keyInformation}
        />
      </IntelligenceCard>

      <IntelligenceCard icon="->" label="Timeline">
        <TimelineList items={timeline} />
      </IntelligenceCard>

      <IntelligenceCard icon="$" label="Financial Summary">
        <KeyValueGrid
          emptyText="Not specified."
          entries={financialSummary}
        />
      </IntelligenceCard>

      <IntelligenceCard icon="=" label="Obligations Matrix">
        <ObligationsMatrix obligations={obligations} />
      </IntelligenceCard>

      <IntelligenceCard icon="§" label="Key Clauses">
        <TagList emptyText="Not specified." items={keyClauses} />
      </IntelligenceCard>

      <IntelligenceCard icon="!" label="Risk Highlights">
        <InsightList emptyText="No major risks detected." items={riskHighlights} tone="risk" />
      </IntelligenceCard>

      <IntelligenceCard icon="?" label="Missing Information">
        <InsightList emptyText="Not specified." items={missingInformation} />
      </IntelligenceCard>

      <IntelligenceCard className="intel-card-wide" icon="+" label="Recommended Questions">
        <div className="intel-question-chips">
          {recommendedQuestions.length > 0 ? (
            recommendedQuestions.map((item, index) => {
              const questionText = displayText(item);
              return (
                <button
                  className="intel-question-chip"
                  disabled={askStatus === "asking"}
                  key={`${questionText}-${index}`}
                  onClick={() => onQuestionClick(questionText)}
                  type="button"
                >
                  {questionText}
                </button>
              );
            })
          ) : (
            <p className="intel-empty">No recommended questions were generated.</p>
          )}
        </div>
      </IntelligenceCard>
    </div>
  );
}

function IntelligenceCard({ children, className = "", icon, label, title }) {
  return (
    <section className={`intel-card ${className}`}>
      <div className="intel-card-heading">
        <span className="intel-card-icon" aria-hidden="true">{icon}</span>
        <div>
          <p>{label}</p>
          {title && <h3>{title}</h3>}
        </div>
      </div>
      {children}
    </section>
  );
}

function KeyValueGrid({ emptyText, entries }) {
  if (!entries.length) return <p className="intel-empty">{emptyText}</p>;

  return (
    <div className="intel-key-grid">
      {entries.map(([key, value]) => (
        <div className="intel-key-item" key={key}>
          <span>{formatLabel(key)}</span>
          <strong>{displayText(value)}</strong>
        </div>
      ))}
    </div>
  );
}

function TimelineList({ items }) {
  if (!items.length) return <p className="intel-empty">Not specified.</p>;

  return (
    <div className="intel-timeline">
      {items.map((item, index) => {
        if (item && typeof item === "object" && !Array.isArray(item)) {
          return (
            <div className="intel-timeline-item" key={`${item.label || "event"}-${index}`}>
              <span>{displayText(item.date || `Step ${index + 1}`)}</span>
              <strong>{displayText(item.label || "Event")}</strong>
              {item.detail && <p>{displayText(item.detail)}</p>}
            </div>
          );
        }

        return (
          <div className="intel-timeline-item" key={`${displayText(item)}-${index}`}>
            <span>Event {index + 1}</span>
            <strong>{displayText(item)}</strong>
          </div>
        );
      })}
    </div>
  );
}

function ObligationsMatrix({ obligations }) {
  const parties = obligations
    .map(([party, value]) => [partyLabel(party, value), obligationItems(value)])
    .filter(([, items]) => items.length > 0);

  if (!parties.length) return <p className="intel-empty">Not specified.</p>;

  return (
    <div className="intel-obligations-grid">
      {parties.map(([party, items]) => (
        <div className="intel-obligation-party" key={party}>
          <span>{formatLabel(party)}</span>
          <ul>
            {items.map((item, index) => (
              <li key={`${displayText(item)}-${index}`}>{displayText(item)}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function TagList({ emptyText, items }) {
  if (!items.length) return <p className="intel-empty">{emptyText}</p>;

  return (
    <div className="intel-tags">
      {items.map((item, index) => (
        <span key={`${displayText(item)}-${index}`}>{displayText(item)}</span>
      ))}
    </div>
  );
}

function InsightList({ emptyText, items, tone = "neutral" }) {
  if (!items.length) return <p className="intel-empty">{emptyText}</p>;

  return (
    <div className={`intel-insight-list ${tone}`}>
      {items.map((item, index) => (
        <div className="intel-insight" key={`${displayText(item)}-${index}`}>
          <span aria-hidden="true">{tone === "risk" ? "!" : "-"}</span>
          <p>{displayText(item)}</p>
        </div>
      ))}
    </div>
  );
}

function buildSnapshot(data) {
  const snapshot = data.snapshot && typeof data.snapshot === "object" ? data.snapshot : {};
  const documentType = firstSpecified(data.documentType, snapshot.documentType, "Document type not specified");
  const confidence = formatConfidencePercentage(firstSpecified(data.confidence, snapshot.estimatedAiConfidence, "Not specified"));

  return {
    documentType,
    items: [
      ["Document Type", documentType],
      ["Confidence", confidence],
      ["Parties", firstSpecified(snapshot.numberOfParties, "Not specified")],
      ["Key Clauses", firstSpecified(snapshot.numberOfMajorClauses, "Not specified")],
      ["Potential Risks", firstSpecified(snapshot.estimatedRiskCount, "Not specified")],
    ].map(([label, value]) => ({ label, value: displayText(value) })),
  };
}

function firstSpecified(...values) {
  return values.find((value) => hasUsableValue(value) && !isNotSpecified(value)) || "Not specified";
}

function normalizedRiskClass(value) {
  const normalized = displayText(value).toLowerCase();
  return ["low", "medium", "high"].includes(normalized) ? normalized : "low";
}

function normalizedDifferenceClass(value) {
  const normalized = displayText(value).toLowerCase();
  return ["added", "removed", "changed", "same"].includes(normalized) ? normalized : "changed";
}

function normalizedRiskChangeClass(value) {
  const normalized = displayText(value).toLowerCase().replace(/\s+/g, "-");
  return ["lower", "same", "higher", "not-applicable"].includes(normalized) ? normalized : "not-applicable";
}

function formatConfidencePercentage(value) {
  if (!hasUsableValue(value) || isNotSpecified(value)) return "Not specified";

  if (typeof value === "number") {
    const percentage = value >= 0 && value <= 1 ? value * 100 : value;
    return `${Math.round(Math.max(0, Math.min(100, percentage)))}%`;
  }

  const normalized = String(value).trim().toLowerCase();
  const confidenceMap = {
    high: "90%",
    medium: "70%",
    low: "45%",
  };

  if (confidenceMap[normalized]) return confidenceMap[normalized];

  const match = normalized.match(/(\d+(?:\.\d+)?)/);
  if (!match) return "Not specified";

  const numericValue = Number(match[1]);
  const percentage = numericValue <= 1 && !normalized.includes("%") ? numericValue * 100 : numericValue;
  return `${Math.round(Math.max(0, Math.min(100, percentage)))}%`;
}

function objectEntries(value, options = {}) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return [];

  return Object.entries(value).filter(([, entryValue]) => {
    if (!hasUsableValue(entryValue)) return false;
    if (options.hideNotSpecified && isNotSpecified(entryValue)) return false;
    return true;
  });
}

function listItems(value) {
  if (Array.isArray(value)) return value.filter(hasUsableValue);
  if (hasUsableValue(value)) return [value];
  return [];
}

function obligationItems(value) {
  if (Array.isArray(value)) return value.filter(hasUsableValue);
  if (!value || typeof value !== "object") return listItems(value);
  if (Array.isArray(value.items)) return value.items.filter(hasUsableValue);
  if (Array.isArray(value.obligations)) return value.obligations.filter(hasUsableValue);
  return objectEntries(value)
    .filter(([key]) => !["name", "party", "role"].includes(key.toLowerCase()))
    .map(([key, entryValue]) => `${formatLabel(key)}: ${displayText(entryValue)}`);
}

function partyLabel(key, value) {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const label = value.name || value.party || value.role;
    if (label && /^party[A-Z]?$/i.test(key)) return displayText(label);
  }
  return formatLabel(key);
}

function hasUsableValue(value) {
  if (value === null || value === undefined) return false;
  if (Array.isArray(value)) return value.some(hasUsableValue);
  if (typeof value === "object") return Object.values(value).some(hasUsableValue);
  return String(value).trim().length > 0;
}

function isNotSpecified(value) {
  if (Array.isArray(value)) return value.every(isNotSpecified);
  if (value && typeof value === "object") return Object.values(value).every(isNotSpecified);
  const normalized = String(value || "").trim().toLowerCase();
  return normalized === "not specified" || normalized === "not applicable";
}

function displayText(value) {
  if (value === null || value === undefined) return "Not specified";
  if (Array.isArray(value)) return value.map(displayText).join(", ");
  if (typeof value === "object") {
    return objectEntries(value)
      .map(([key, entryValue]) => `${formatLabel(key)}: ${displayText(entryValue)}`)
      .join("; ") || "Not specified";
  }
  return String(value);
}

function formatLabel(value) {
  return String(value)
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase())
    .replace(/\bAi\b/g, "AI")
    .replace(/\bIp\b/g, "IP");
}

function MarkdownView({ markdown }) {
  const elements = [];
  let paragraph = [];
  let list = [];

  function flushParagraph() {
    if (!paragraph.length) return;
    const lines = paragraph;
    elements.push(
      <p key={`p-${elements.length}`}>
        {lines.map((line, index) => (
          <span key={index}>
            {renderInlineMarkdown(line)}
            {index < lines.length - 1 && <br />}
          </span>
        ))}
      </p>,
    );
    paragraph = [];
  }

  function flushList() {
    if (!list.length) return;
    const items = list;
    elements.push(
      <ul key={`ul-${elements.length}`}>
        {items.map((item, index) => (
          <li key={index}>{renderInlineMarkdown(item)}</li>
        ))}
      </ul>,
    );
    list = [];
  }

  markdown.split("\n").forEach((rawLine) => {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      flushList();
      return;
    }

    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      flushList();
      const level = heading[1].length;
      const text = heading[2];
      if (level === 1) elements.push(<h2 key={`h-${elements.length}`}>{text}</h2>);
      else if (level === 2) elements.push(<h3 key={`h-${elements.length}`}>{text}</h3>);
      else elements.push(<h4 key={`h-${elements.length}`}>{text}</h4>);
      return;
    }

    const listItem = line.match(/^[-*]\s+(.+)$/);
    if (listItem) {
      flushParagraph();
      list.push(listItem[1]);
      return;
    }

    flushList();
    paragraph.push(line);
  });

  flushParagraph();
  flushList();

  return elements;
}

function renderInlineMarkdown(text) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    return part;
  });
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
