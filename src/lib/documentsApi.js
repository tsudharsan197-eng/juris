import { getCurrentSession } from "./supabase.js";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function accessToken() {
  const { data, error } = await getCurrentSession();
  if (error) throw error;
  const token = data?.session?.access_token;
  if (!token) throw new Error("Please sign in before uploading documents.");
  return token;
}

async function apiFetch(path, options = {}) {
  const token = await accessToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options.headers || {}),
    },
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || body.message || "Document API request failed.");
  }
  return body;
}

export async function uploadDocumentFile(file, onProgress) {
  const token = await accessToken();
  const formData = new FormData();
  formData.append("file", file);
  onProgress?.(18);

  const response = await fetch(`${API_BASE_URL}/api/documents/upload`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });

  onProgress?.(82);

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || body.message || "Document upload failed.");
  }

  onProgress?.(100);
  return body;
}

export function listDocuments() {
  return apiFetch("/api/documents");
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
