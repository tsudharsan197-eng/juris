import { getCurrentSession } from "./supabase.js";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function accessToken() {
  const { data, error } = await getCurrentSession();
  if (error) throw error;
  const token = data?.session?.access_token;
  if (!token) throw new Error("Please sign in to use Juris Compass.");
  return token;
}

async function compassFetch(path, options = {}) {
  const token = await accessToken();
  const startedAt = performance.now();
  console.info("[Juris Compass request:start]", { endpoint: path, method: options.method || "GET" });

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
    if (error?.name === "AbortError") throw error;
    console.error("[Juris Compass request:network-error]", { endpoint: path, error });
    throw new Error("Backend unavailable. Juris Compass could not reach the legal research service.");
  }

  const text = await response.text();
  let body = {};
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = { detail: text };
    }
  }

  console.info("[Juris Compass request:finish]", {
    endpoint: path,
    status: response.status,
    durationMs: Math.round(performance.now() - startedAt),
    body,
  });

  if (!response.ok || body?.success === false) {
    const backendError = body?.error;
    const message = typeof backendError === "object"
      ? backendError.message
      : body?.detail || body?.message || "Juris Compass request failed.";
    const error = new Error(message || "Juris Compass request failed.");
    error.backendType = backendError?.type || body?.type;
    error.requestId = backendError?.requestId || body?.requestId;
    throw error;
  }

  return body?.success === true ? body.data : body;
}

export function askCompass({ message, jurisdiction, conversationId }, options = {}) {
  return compassFetch("/api/juris-compass/chat", {
    ...options,
    method: "POST",
    body: JSON.stringify({
      message,
      jurisdiction,
      conversation_id: conversationId || null,
    }),
  });
}

export function listCompassConversations(options = {}) {
  return compassFetch("/api/juris-compass/conversations", options);
}

export function getCompassConversation(conversationId, options = {}) {
  return compassFetch(`/api/juris-compass/conversations/${conversationId}`, options);
}

export function updateCompassConversation(conversationId, updates, options = {}) {
  return compassFetch(`/api/juris-compass/conversations/${conversationId}`, {
    ...options,
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

export function deleteCompassConversation(conversationId, options = {}) {
  return compassFetch(`/api/juris-compass/conversations/${conversationId}`, {
    ...options,
    method: "DELETE",
  });
}
