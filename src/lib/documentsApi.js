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

export function presignDocumentUpload(file) {
  return apiFetch("/api/documents/presign-upload", {
    method: "POST",
    body: JSON.stringify({
      fileName: file.name,
      contentType: normalizedContentType(file),
      fileSize: file.size,
    }),
  });
}

export function completeDocumentUpload({ documentId, fileKey, file }) {
  return apiFetch("/api/documents/complete-upload", {
    method: "POST",
    body: JSON.stringify({
      documentId,
      fileKey,
      fileName: file.name,
      fileSize: file.size,
      contentType: normalizedContentType(file),
    }),
  });
}

export function listDocuments() {
  return apiFetch("/api/documents");
}

export async function uploadFileToSignedUrl(uploadUrl, file, onProgress) {
  onProgress?.(35);

  const response = await fetch(uploadUrl, {
    method: "PUT",
    body: file,
  });

  if (!response.ok) {
    throw new Error(`R2 upload failed with status ${response.status}.`);
  }

  onProgress?.(100);
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
