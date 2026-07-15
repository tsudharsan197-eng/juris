import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  ArrowRight,
  BookOpen,
  Check,
  Compass as CompassIcon,
  ExternalLink,
  History,
  Menu,
  Pencil,
  Plus,
  Scale,
  Trash2,
  X,
} from "lucide-react";
import Button from "./Button.jsx";
import { useAuth } from "./AuthProvider.jsx";
import {
  askCompass,
  deleteCompassConversation,
  getCompassConversation,
  listCompassConversations,
  updateCompassConversation,
} from "../lib/compassApi.js";

const JURISDICTIONS = [
  "India",
  "United States",
  "United Kingdom",
  "European Union",
  "Australia",
  "Canada",
  "Other",
];

const SUGGESTED_QUESTIONS = [
  "What is the Indian Contract Act?",
  "Explain Section 73.",
  "How does arbitration differ from litigation?",
  "What is force majeure?",
  "What is promissory estoppel?",
];

const RESEARCH_STAGES = [
  "Checking jurisdiction",
  "Reviewing applicable law",
  "Verifying current provisions",
  "Preparing plain English explanation",
  "Attaching sources",
];

const ANSWER_SECTIONS = [
  ["directAnswer", "Direct answer"],
  ["plainEnglish", "Plain English"],
  ["legalBasis", "Legal basis"],
  ["importantExceptions", "Important exceptions"],
  ["practicalNotes", "Practical notes"],
  ["authoritativeSources", "Authoritative sources"],
];

function localMessageId() {
  return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function formattedDate(value) {
  if (!value) return "Current date";
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

function messageSections(message) {
  const sections = message.data?.sections;
  if (sections && Object.values(sections).some(Boolean)) return sections;
  return { directAnswer: message.content };
}

export default function JurisCompass({ embedded = false }) {
  const { isSignedIn, loading: authLoading } = useAuth();
  const reduceMotion = useReducedMotion();
  const [jurisdiction, setJurisdiction] = useState("India");
  const [conversationId, setConversationId] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [historyStatus, setHistoryStatus] = useState("idle");
  const [historyOpen, setHistoryOpen] = useState(false);
  const [contextOpen, setContextOpen] = useState(false);
  const [renamingId, setRenamingId] = useState(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleteConfirmId, setDeleteConfirmId] = useState(null);
  const [researchStage, setResearchStage] = useState(0);
  const historyRequestedRef = useRef(false);
  const activeRequestRef = useRef(null);
  const threadRef = useRef(null);

  const latestAssistant = useMemo(
    () => [...messages].reverse().find((message) => message.role === "assistant"),
    [messages],
  );
  const currentSources = latestAssistant?.data?.sources || [];

  useEffect(() => {
    if (authLoading) return;
    if (!isSignedIn) {
      historyRequestedRef.current = false;
      setConversations([]);
      setMessages([]);
      setConversationId(null);
      return;
    }
    if (historyRequestedRef.current) return;
    historyRequestedRef.current = true;
    void refreshConversations();
  }, [authLoading, isSignedIn]);

  useEffect(() => () => activeRequestRef.current?.abort(), []);

  useEffect(() => {
    if (status !== "researching") {
      setResearchStage(0);
      return undefined;
    }
    const timer = window.setInterval(() => {
      setResearchStage((current) => Math.min(current + 1, RESEARCH_STAGES.length - 1));
    }, 900);
    return () => window.clearInterval(timer);
  }, [status]);

  useEffect(() => {
    const thread = threadRef.current;
    if (!thread) return;
    const frame = window.requestAnimationFrame(() => {
      thread.scrollTo({ top: thread.scrollHeight, behavior: reduceMotion ? "auto" : "smooth" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [messages, reduceMotion, status]);

  async function refreshConversations() {
    setHistoryStatus("loading");
    try {
      const items = await listCompassConversations();
      setConversations(items || []);
      setHistoryStatus("ready");
    } catch (nextError) {
      if (nextError.name === "AbortError") return;
      setHistoryStatus("error");
      setError(nextError.message || "Compass history could not be loaded.");
    }
  }

  function startNewConversation() {
    activeRequestRef.current?.abort();
    activeRequestRef.current = null;
    setConversationId(null);
    setMessages([]);
    setQuestion("");
    setError("");
    setStatus("idle");
    setHistoryOpen(false);
  }

  async function selectConversation(nextConversation) {
    if (status === "researching") return;
    const controller = new AbortController();
    activeRequestRef.current?.abort();
    activeRequestRef.current = controller;
    setConversationId(nextConversation.id);
    setJurisdiction(nextConversation.jurisdiction);
    setStatus("loading-conversation");
    setError("");
    setHistoryOpen(false);

    try {
      const result = await getCompassConversation(nextConversation.id, { signal: controller.signal });
      if (activeRequestRef.current !== controller) return;
      setMessages(result.messages || []);
      setJurisdiction(result.jurisdiction || nextConversation.jurisdiction);
      setStatus("idle");
    } catch (nextError) {
      if (nextError.name === "AbortError") return;
      setError(nextError.message || "This Compass conversation could not be opened.");
      setStatus("error");
    } finally {
      if (activeRequestRef.current === controller) activeRequestRef.current = null;
    }
  }

  async function submitQuestion(value) {
    const nextQuestion = String(value || "").trim();
    if (!nextQuestion || status === "researching") return;

    const controller = new AbortController();
    activeRequestRef.current?.abort();
    activeRequestRef.current = controller;
    const userMessage = { id: localMessageId(), role: "user", content: nextQuestion };
    setMessages((current) => [...current, userMessage]);
    setQuestion("");
    setError("");
    setStatus("researching");

    try {
      const result = await askCompass({
        message: nextQuestion,
        jurisdiction,
        conversationId,
      }, { signal: controller.signal });
      if (activeRequestRef.current !== controller) return;
      setConversationId(result.conversationId);
      setMessages((current) => [
        ...current,
        {
          id: localMessageId(),
          role: "assistant",
          content: result.answer,
          data: result,
        },
      ]);
      setStatus("idle");
      await refreshConversations();
    } catch (nextError) {
      if (nextError.name === "AbortError") return;
      setError(nextError.message || "Juris Compass could not complete this legal research.");
      setStatus("error");
    } finally {
      if (activeRequestRef.current === controller) activeRequestRef.current = null;
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    void submitQuestion(question);
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  async function handleJurisdictionChange(event) {
    const nextJurisdiction = event.target.value;
    setJurisdiction(nextJurisdiction);
    setError("");
    if (!conversationId) return;
    try {
      await updateCompassConversation(conversationId, { jurisdiction: nextJurisdiction });
      setConversations((current) => current.map((item) => (
        item.id === conversationId ? { ...item, jurisdiction: nextJurisdiction } : item
      )));
    } catch (nextError) {
      setError(nextError.message || "The conversation jurisdiction could not be updated.");
    }
  }

  function beginRename(conversation) {
    setRenamingId(conversation.id);
    setRenameValue(conversation.title);
    setDeleteConfirmId(null);
  }

  async function finishRename(event, id) {
    event.preventDefault();
    const title = renameValue.trim();
    if (title.length < 2) return;
    try {
      const updated = await updateCompassConversation(id, { title });
      setConversations((current) => current.map((item) => (item.id === id ? { ...item, ...updated } : item)));
      setRenamingId(null);
      setRenameValue("");
    } catch (nextError) {
      setError(nextError.message || "The conversation could not be renamed.");
    }
  }

  async function handleDelete(id) {
    if (deleteConfirmId !== id) {
      setDeleteConfirmId(id);
      setRenamingId(null);
      return;
    }
    try {
      await deleteCompassConversation(id);
      setConversations((current) => current.filter((item) => item.id !== id));
      if (conversationId === id) startNewConversation();
      setDeleteConfirmId(null);
    } catch (nextError) {
      setError(nextError.message || "The conversation could not be deleted.");
    }
  }

  return (
    <section className={`compass-product${embedded ? " is-embedded" : " is-standalone"}`} data-testid="juris-compass">
      <CompassHeader
        embedded={embedded}
        historyOpen={historyOpen}
        jurisdiction={jurisdiction}
        onContextToggle={() => setContextOpen((open) => !open)}
        onHistoryToggle={() => setHistoryOpen((open) => !open)}
        onJurisdictionChange={handleJurisdictionChange}
        showWorkspaceControls={!authLoading && isSignedIn}
        status={status}
      />

      {authLoading ? (
        <div className="compass-auth-state is-loading" role="status">
          <span>Secure session</span>
          <CompassIcon aria-hidden="true" size={32} strokeWidth={1.4} />
          <h2>Opening the legal research system.</h2>
          <p>Verifying your Juris session before loading private Compass conversations.</p>
        </div>
      ) : !isSignedIn ? (
        <div className="compass-auth-state">
          <span>Authentication required</span>
          <CompassIcon aria-hidden="true" size={32} strokeWidth={1.4} />
          <h2>Legal research starts with secure access.</h2>
          <p>Sign in to create private Compass conversations. No document upload is required.</p>
          <Button to="/sign-in">Sign In</Button>
        </div>
      ) : (
        <div className="compass-layout">
          <button
            className={`compass-drawer-scrim${historyOpen || contextOpen ? " visible" : ""}`}
            type="button"
            aria-label="Close Compass drawer"
            onClick={() => {
              setHistoryOpen(false);
              setContextOpen(false);
            }}
          />

          <aside className={`compass-history${historyOpen ? " open" : ""}`} aria-label="Compass conversation history">
            <div className="compass-panel-heading">
              <div><History aria-hidden="true" size={15} /><span>{embedded ? "History" : "Research index"}</span></div>
              <button type="button" onClick={startNewConversation} aria-label="Start a new Compass conversation">
                <Plus aria-hidden="true" size={15} /> New
              </button>
            </div>
            <div className="compass-history-list">
              {historyStatus === "loading" && <p className="compass-history-note">Loading research history...</p>}
              {historyStatus !== "loading" && conversations.length === 0 && (
                <p className="compass-history-note">No saved research yet. Ask your first legal question.</p>
              )}
              {conversations.map((conversation, index) => (
                <article className={`compass-history-row${conversation.id === conversationId ? " active" : ""}`} key={conversation.id}>
                  {renamingId === conversation.id ? (
                    <form onSubmit={(event) => finishRename(event, conversation.id)}>
                      <input
                        aria-label="Conversation title"
                        autoFocus
                        value={renameValue}
                        onChange={(event) => setRenameValue(event.target.value)}
                        maxLength={80}
                      />
                      <button type="submit" aria-label="Save conversation title"><Check size={14} /></button>
                      <button type="button" aria-label="Cancel rename" onClick={() => setRenamingId(null)}><X size={14} /></button>
                    </form>
                  ) : (
                    <>
                      <button className="compass-history-select" type="button" onClick={() => selectConversation(conversation)}>
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        <strong>{conversation.title}</strong>
                        <small>{conversation.jurisdiction} · {conversation.messageCount} messages</small>
                      </button>
                      <div className="compass-history-actions">
                        <button type="button" aria-label={`Rename ${conversation.title}`} onClick={() => beginRename(conversation)}><Pencil size={13} /></button>
                        <button
                          className={deleteConfirmId === conversation.id ? "confirm" : ""}
                          type="button"
                          aria-label={deleteConfirmId === conversation.id ? `Confirm delete ${conversation.title}` : `Delete ${conversation.title}`}
                          onClick={() => handleDelete(conversation.id)}
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </>
                  )}
                </article>
              ))}
            </div>
            <p className="compass-history-footer">Compass memory is separate from document chat.</p>
          </aside>

          <div className="compass-research-canvas">
            <div className="compass-thread" ref={threadRef} aria-live="polite">
              {status === "loading-conversation" && (
                <div className="compass-inline-status">Opening legal research...</div>
              )}

              {messages.length === 0 && status !== "loading-conversation" && (
                <CompassEmptyState onSelect={submitQuestion} />
              )}

              <AnimatePresence initial={false}>
                {messages.map((message, index) => (
                  message.role === "user" ? (
                    <motion.article
                      className="compass-question"
                      key={message.id}
                      initial={reduceMotion ? { opacity: 0 } : { opacity: 0, x: -14 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: reduceMotion ? .12 : .32 }}
                    >
                      <span>{embedded ? "You" : `Query / ${String(index + 1).padStart(2, "0")}`}</span>
                      <p>{message.content}</p>
                    </motion.article>
                  ) : (
                    <CompassAnswer compact={embedded} key={message.id} message={message} reduceMotion={reduceMotion} />
                  )
                ))}
              </AnimatePresence>

              {status === "researching" && <CompassResearching compact={embedded} stage={researchStage} />}
            </div>

            {error && (
              <div className="compass-error" role="alert">
                <span>Research interrupted</span>
                <p>{error}</p>
                <button type="button" onClick={() => setError("")}>Dismiss</button>
              </div>
            )}

            <form className="compass-composer" onSubmit={handleSubmit}>
              <div className="compass-composer-meta">
                <span>Ask Compass</span>
                <small>{embedded ? `${jurisdiction} · Sources included` : `${jurisdiction} / Jurisdiction-grounded`}</small>
              </div>
              <div className="compass-composer-input">
                <textarea
                  aria-label="Ask Juris Compass"
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask about a law, Act, section, procedure, or legal concept..."
                  rows={1}
                />
                <button type="submit" disabled={status === "researching" || !question.trim()}>
                  <span>{status === "researching" ? "Checking law" : "Ask Compass"}</span>
                  <ArrowRight aria-hidden="true" size={17} />
                </button>
              </div>
              <p>Juris Compass provides legal information and education. It is not legal advice.</p>
            </form>
          </div>

          <CompassContext
            className={contextOpen ? "open" : ""}
            compact={embedded}
            jurisdiction={jurisdiction}
            sources={currentSources}
            verificationStatus={latestAssistant?.data?.verificationStatus}
          />
        </div>
      )}
    </section>
  );
}

function CompassHeader({ embedded, historyOpen, jurisdiction, onContextToggle, onHistoryToggle, onJurisdictionChange, showWorkspaceControls, status }) {
  return (
    <header className={`compass-header${embedded ? " workspace-tool-header" : ""}`}>
      {!embedded && (
        <div className="workspace-tool-index compass-system-index">
          <span>Juris Compass</span>
          <i aria-hidden="true" />
        </div>
      )}
      <div className="compass-header-copy">
        <h1>{embedded ? "Juris Compass" : "Navigate the law with confidence."}</h1>
        <p>{embedded ? "Ask about laws, Acts, legal concepts, rights, and procedures beyond this document." : "Ask about Acts, statutes, legal concepts, procedures, rights, and legal principles. Answers use jurisdiction and verified legal sources, never an uploaded document."}</p>
      </div>
      <div className="compass-header-controls">
        <label>
          <span>Jurisdiction</span>
          <select value={jurisdiction} onChange={onJurisdictionChange} disabled={status === "researching"}>
            {JURISDICTIONS.map((item) => <option value={item} key={item}>{item}</option>)}
          </select>
        </label>
        {!embedded && (
          <div className="compass-global-state">
            <span><CompassIcon aria-hidden="true" size={13} /> Global research</span>
            <small>Verified law</small>
          </div>
        )}
        {showWorkspaceControls && (
          <div className="compass-mobile-tools">
            <button type="button" aria-label={historyOpen ? "Close research history" : "Open research history"} onClick={onHistoryToggle}>
              {historyOpen ? <X size={16} /> : <Menu size={16} />} History
            </button>
            <button type="button" onClick={onContextToggle}><Scale size={16} /> Context</button>
          </div>
        )}
      </div>
    </header>
  );
}

function CompassEmptyState({ onSelect }) {
  return (
    <div className="compass-empty-state">
      <div className="compass-empty-intro">
        <span>Start with the law</span>
        <CompassIcon aria-hidden="true" size={32} strokeWidth={1.3} />
        <h2>Understand law without opening a document.</h2>
        <p>Research Acts, sections, doctrines, procedures, rights, and legal terminology using a selected jurisdiction.</p>
      </div>
      <div className="compass-suggestions" aria-label="Suggested Compass questions">
        {SUGGESTED_QUESTIONS.map((prompt, index) => (
          <button type="button" key={prompt} onClick={() => onSelect(prompt)}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <strong>{prompt}</strong>
            <ArrowRight aria-hidden="true" size={15} />
          </button>
        ))}
      </div>
    </div>
  );
}

function CompassAnswer({ compact = false, message, reduceMotion }) {
  const sections = messageSections(message);
  const sources = message.data?.sources || [];
  return (
    <motion.article
      className="compass-answer"
      initial={reduceMotion ? { opacity: 0 } : { opacity: 0, y: 16, clipPath: "inset(0 0 12% 0)" }}
      animate={{ opacity: 1, y: 0, clipPath: "inset(0 0 0% 0)" }}
      transition={{ duration: reduceMotion ? .12 : .46, ease: [.22, .8, .36, 1] }}
    >
      <div className="compass-answer-register">
        <span>Juris Compass</span>
        <span>{compact ? message.data?.jurisdiction || "Jurisdiction not specified" : `Jurisdiction / ${message.data?.jurisdiction || "Not specified"}`}</span>
        <span>{compact ? `Checked ${formattedDate(message.data?.checkedAt)}` : `Checked / ${formattedDate(message.data?.checkedAt)}`}</span>
        <span>{sources.length ? `${sources.length} sources` : "Sources unavailable"}</span>
      </div>
      <div className="compass-answer-sections">
        {ANSWER_SECTIONS.map(([key, label], index) => {
          const content = sections[key];
          if (!content && key !== "authoritativeSources") return null;
          return (
            <section className={`compass-answer-section section-${key}`} key={key}>
              <div><span>{String(index + 1).padStart(2, "0")}</span><h3>{label}</h3></div>
              {content && <p>{content}</p>}
              {key === "authoritativeSources" && (
                <div className="compass-inline-sources">
                  {sources.length ? sources.map((source) => (
                    <a href={source.url} target="_blank" rel="noreferrer" key={source.url}>
                      <span>{source.domain}</span>
                      <strong>{source.title}</strong>
                      <ExternalLink aria-hidden="true" size={13} />
                    </a>
                  )) : <small>No verified source URL was returned. Treat this answer as unverified.</small>}
                </div>
              )}
            </section>
          );
        })}
      </div>
      <p className="compass-answer-disclaimer">{message.data?.disclaimer || "Legal information only. Not legal advice."}</p>
    </motion.article>
  );
}

function CompassResearching({ compact = false, stage }) {
  return (
    <div className="compass-researching" role="status">
      <div>
        <CompassIcon aria-hidden="true" size={22} strokeWidth={1.4} />
        <span>{compact ? "Juris Compass" : "Juris processing system"}</span>
        <h3>{compact ? "Researching the law." : "Researching applicable law."}</h3>
      </div>
      <ol>
        {RESEARCH_STAGES.map((item, index) => (
          <li className={index < stage ? "complete" : index === stage ? "active" : ""} key={item}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <strong>{item}</strong>
            <i aria-hidden="true" />
          </li>
        ))}
      </ol>
    </div>
  );
}

function CompassContext({ className = "", compact = false, jurisdiction, sources, verificationStatus }) {
  return (
    <aside className={`compass-context ${className}`.trim()} aria-label="Compass legal context">
      <div className="compass-panel-heading">
        <div><Scale aria-hidden="true" size={15} /><span>{compact ? "Sources and jurisdiction" : "Legal context"}</span></div>
      </div>
      {compact ? (
        <dl>
          <div><dt>Jurisdiction</dt><dd>{jurisdiction}</dd></div>
          <div><dt>Sources</dt><dd>{sources.length ? `${sources.length} available` : "Included with answers"}</dd></div>
          <div><dt>Status</dt><dd className={sources.length ? "verified" : "ready"}>{verificationStatus || "Ready"}</dd></div>
        </dl>
      ) : (
        <dl>
          <div><dt>Jurisdiction</dt><dd>{jurisdiction}</dd></div>
          <div><dt>Research mode</dt><dd>Verified legal sources</dd></div>
          <div><dt>Document dependency</dt><dd>None</dd></div>
          <div><dt>Source system</dt><dd>Official law and public authorities</dd></div>
          <div><dt>Status</dt><dd className={sources.length ? "verified" : "ready"}>{verificationStatus || "Ready"}</dd></div>
        </dl>
      )}
      <div className="compass-source-ledger">
        <span>{compact ? `Sources (${sources.length})` : `Active sources / ${String(sources.length).padStart(2, "0")}`}</span>
        {sources.length ? sources.map((source, index) => (
          <a href={source.url} target="_blank" rel="noreferrer" key={source.url}>
            <small>{String(index + 1).padStart(2, "0")}</small>
            <strong>{source.title}</strong>
            <span>{source.domain}</span>
            <ExternalLink aria-hidden="true" size={12} />
          </a>
        )) : (
          <p>Verified source links will appear after the first Compass answer.</p>
        )}
      </div>
      <div className="compass-context-note">
        <BookOpen aria-hidden="true" size={16} />
        <p>Laws change. Check the cited authority and consult a qualified professional for advice about a specific matter.</p>
      </div>
    </aside>
  );
}
