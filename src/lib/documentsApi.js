import { getCurrentSession } from "./supabase.js";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function startRequestLog(path, options = {}) {
  const startedAt = Date.now();
  const method = options.method || "GET";
  console.info("[Juris API request:start]", {
    endpoint: path,
    method,
    startTime: new Date(startedAt).toISOString(),
  });
  return { method, path, startedAt };
}

function finishRequestLog(requestLog, response, body, error) {
  const finishedAt = Date.now();
  console.info("[Juris API request:finish]", {
    endpoint: requestLog.path,
    method: requestLog.method,
    startTime: new Date(requestLog.startedAt).toISOString(),
    finishTime: new Date(finishedAt).toISOString(),
    durationMs: finishedAt - requestLog.startedAt,
    status: response?.status || null,
    ok: response?.ok || false,
    body,
    error: error?.message || null,
  });
}

function backendUnavailableError(error, path) {
  const nextError = new Error("Backend unavailable. Make sure the FastAPI backend is running.");
  nextError.detail = nextError.message;
  nextError.backendError = error.message;
  nextError.backendType = error.name || "NetworkError";
  nextError.endpoint = path;
  return nextError;
}

async function accessToken() {
  const { data, error } = await getCurrentSession();
  if (error) throw error;
  const token = data?.session?.access_token;
  if (!token) throw new Error("Please sign in before uploading documents.");
  return token;
}

async function apiFetch(path, options = {}) {
  const token = await accessToken();
  const requestLog = startRequestLog(path, options);
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...(options.headers || {}),
      },
    });
  } catch (error) {
    finishRequestLog(requestLog, null, null, error);
    throw backendUnavailableError(error, path);
  }

  const body = await parseResponseBody(response);
  finishRequestLog(requestLog, response, body);
  if (!response.ok || body?.success === false) {
    throw apiError(body, "Document API request failed.");
  }
  return body?.success === true ? body.data : body;
}

async function apiTextFetch(path, options = {}) {
  const token = await accessToken();
  const requestLog = startRequestLog(path, options);
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...(options.headers || {}),
      },
    });
  } catch (error) {
    finishRequestLog(requestLog, null, null, error);
    throw backendUnavailableError(error, path);
  }

  const text = await response.text();
  finishRequestLog(requestLog, response, text);
  if (!response.ok) {
    let body = {};
    try {
      body = JSON.parse(text);
    } catch {
      body = { detail: text || "Document API request failed." };
    }
    throw apiError(body, "Document API request failed.");
  }
  return text;
}

async function parseResponseBody(response) {
  const text = await response.text();
  if (!text) return {};

  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

function apiError(body, fallback) {
  const envelopeError = body?.error && typeof body.error === "object" ? body.error : null;
  const detail = envelopeError?.message || body.detail || body.message || fallback;
  const backendError = envelopeError ? envelopeError.details : body.error;
  const backendType = envelopeError?.type || body.type;
  const requestId = envelopeError?.requestId || body.requestId;
  const diagnostic = backendError
    ? `${backendType || "Error"}: ${typeof backendError === "string" ? backendError : JSON.stringify(backendError)}`
    : "";
  const error = new Error(diagnostic ? `${detail} - ${diagnostic}` : detail);
  error.detail = detail;
  error.backendError = backendError;
  error.backendType = backendType;
  error.requestId = requestId;
  return error;
}

export async function uploadDocumentFile(file, onProgress) {
  const token = await accessToken();
  const formData = new FormData();
  formData.append("file", file);
  const endpoint = "/api/documents/upload";
  const requestLog = startRequestLog(endpoint, { method: "POST" });

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    });
  } catch (error) {
    finishRequestLog(requestLog, null, null, error);
    throw backendUnavailableError(error, endpoint);
  }

  const body = await response.json().catch(() => ({}));
  finishRequestLog(requestLog, response, body);
  if (!response.ok) {
    throw apiError(body, "Document upload failed.");
  }

  onProgress?.(100);
  return body;
}

export function reprocessDocument(documentId) {
  return apiFetch(`/api/documents/${documentId}/reprocess`, {
    method: "POST",
  });
}

export function listDocuments() {
  return apiFetch("/api/documents");
}

export function deleteDocument(documentId) {
  return apiFetch(`/api/documents/${documentId}`, {
    method: "DELETE",
  });
}

export function getDocumentDownloadUrl(documentId) {
  return apiFetch(`/api/documents/${documentId}/download-url`);
}

export function askDocumentQuestion(documentId, question) {
  return apiFetch(`/api/documents/${documentId}/ask`, {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

export async function getDocumentSummary(documentId, options = {}) {
  const data = await apiFetch(`/api/documents/${documentId}/summary`, {
    ...options,
    method: "POST",
  });
  return data?.summary || "";
}

export function getDocumentIntelligence(documentId, options = {}) {
  return apiFetch(`/api/documents/${documentId}/intelligence`, {
    ...options,
    method: "POST",
  });
}

export function getDocumentClauses(documentId, options = {}) {
  return apiFetch(`/api/documents/${documentId}/clauses`, {
    ...options,
    method: "POST",
  });
}

export function getDocumentRiskAnalysis(documentId, options = {}) {
  return apiFetch(`/api/documents/${documentId}/risk-analysis`, {
    ...options,
    method: "POST",
  });
}

export function compareDocuments(documentId, secondDocumentId, options = {}) {
  return apiFetch(`/api/documents/${documentId}/compare`, {
    ...options,
    method: "POST",
    body: JSON.stringify({ second_document_id: secondDocumentId }),
  });
}

export function normalizedContentType(file) {
  const extension = file.name.split(".").pop()?.toLowerCase();
  if (extension === "pdf") return "application/pdf";
  if (extension === "doc") return "application/msword";
  if (extension === "docx") {
    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  }
  return file.type || "application/octet-stream";
}
