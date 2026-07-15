import asyncio
import hashlib
import io
import json
import math
import os
import re
import time
import traceback
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Annotated
from urllib.parse import urlparse

import asyncpg
import boto3
import httpx
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, OpenAIError
from pypdf import PdfReader
from pydantic import BaseModel

load_dotenv()

MAX_FILE_SIZE = 25 * 1024 * 1024
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-5-mini")
OPENAI_ANALYSIS_MODEL = os.getenv("OPENAI_ANALYSIS_MODEL", "gpt-5-mini")
OPENAI_COMPASS_MODEL = os.getenv("OPENAI_COMPASS_MODEL", OPENAI_CHAT_MODEL)
EMBEDDING_DIMENSIONS = 1536
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "16"))
AI_TIMEOUT_SECONDS = int(os.getenv("OPENAI_TIMEOUT_SECONDS", os.getenv("AI_TIMEOUT_SECONDS", "120")))
COMPARE_TIMEOUT_SECONDS = int(os.getenv("OPENAI_COMPARE_TIMEOUT_SECONDS", "180"))
COMPARE_MAX_OUTPUT_TOKENS = int(os.getenv("OPENAI_COMPARE_MAX_OUTPUT_TOKENS", "1800"))
COMPARE_CONTEXT_CHAR_BUDGET = int(os.getenv("COMPARE_CONTEXT_CHAR_BUDGET", "8000"))
COMPARE_MAX_CHUNKS_PER_DOCUMENT = int(os.getenv("COMPARE_MAX_CHUNKS_PER_DOCUMENT", "8"))
COMPASS_MAX_MESSAGE_CHARS = 4000
COMPASS_HISTORY_LIMIT = 10
COMPASS_MAX_OUTPUT_TOKENS = int(os.getenv("OPENAI_COMPASS_MAX_OUTPUT_TOKENS", "2500"))
COMPASS_DISCLAIMER = (
    "Juris Compass provides legal information and education. It is not legal advice. "
    "Laws vary across jurisdictions and may change. Consult a qualified legal professional "
    "for advice about your specific situation."
)
COMPASS_JURISDICTIONS = (
    "India",
    "United States",
    "United Kingdom",
    "European Union",
    "Australia",
    "Canada",
    "Other",
)
COMPASS_SOURCE_DOMAINS = {
    "India": [
        "indiacode.nic.in",
        "legislative.gov.in",
        "egazette.nic.in",
        "sci.gov.in",
        "rbi.org.in",
        "sebi.gov.in",
    ],
    "United States": [
        "congress.gov",
        "uscode.house.gov",
        "supremecourt.gov",
        "govinfo.gov",
        "federalregister.gov",
    ],
    "United Kingdom": [
        "legislation.gov.uk",
        "gov.uk",
        "judiciary.uk",
        "bailii.org",
    ],
    "European Union": [
        "eur-lex.europa.eu",
        "curia.europa.eu",
        "europa.eu",
    ],
    "Australia": [
        "legislation.gov.au",
        "hcourt.gov.au",
        "fedcourt.gov.au",
        "austlii.edu.au",
    ],
    "Canada": [
        "laws-lois.justice.gc.ca",
        "scc-csc.ca",
        "canada.ca",
        "gazette.gc.ca",
    ],
}
SUPPORTED_TYPES = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}
SUPPORTED_EXTENSIONS = {".pdf", ".doc", ".docx"}
EXTENSION_CONTENT_TYPES = {extension: mime_type for mime_type, extension in SUPPORTED_TYPES.items()}

app = FastAPI(title="Juris Document API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://juris-pi.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AIProviderError(Exception):
    def __init__(
        self,
        message: str,
        *,
        error_type: str = "AIProviderError",
        model: str | None = None,
        status_code: int = 502,
        raw_response: str | None = None,
    ):
        super().__init__(message)
        self.error_type = error_type
        self.model = model
        self.status_code = status_code
        self.raw_response = raw_response


def request_id() -> str:
    return uuid.uuid4().hex[:12]


def success_envelope(data, request_id_value: str):
    return {
        "success": True,
        "data": data,
        "error": None,
        "requestId": request_id_value,
    }


def error_envelope_response(
    *,
    message: str,
    request_id_value: str,
    status_code_value: int = 500,
    error_type: str = "ServerError",
    details=None,
):
    content = {
        "success": False,
        "data": None,
        "error": {
            "message": message,
            "type": error_type,
            "details": details,
            "requestId": request_id_value,
        },
        "requestId": request_id_value,
    }
    print(
        f"[api:error] request_id={request_id_value} status={status_code_value} "
        f"type={error_type} message={message} details={details}"
    )
    return JSONResponse(status_code=status_code_value, content=content)


def log_exception(stage: str, exc: Exception, request_id_value: str, **context):
    print(
        f"[backend:exception] request_id={request_id_value} stage={stage} "
        f"type={exc.__class__.__name__} message={exc} context={context}"
    )
    traceback.print_exc()


def sanitize_log_text(value: str | None, limit: int = 8000) -> str:
    if value is None:
        return ""
    if len(value) <= limit:
        return value
    return f"{value[:limit]}... [truncated {len(value) - limit} chars]"


def upstream_status_from_exception(exc: Exception) -> int:
    for attribute in ("status_code", "code"):
        value = getattr(exc, attribute, None)
        if isinstance(value, int):
            return value
    message = str(exc).lower()
    if "429" in message or "quota" in message or "rate limit" in message:
        return 429
    if "401" in message or "403" in message or "permission" in message or "api key" in message:
        return 502
    return 502


@app.middleware("http")
async def log_http_requests(request: Request, call_next):
    started_at = time.perf_counter()
    req_id = request.headers.get("x-request-id") or request_id()
    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started_at) * 1000)
        log_exception("http_request", exc, req_id, path=request.url.path, duration_ms=duration_ms)
        raise

    duration_ms = round((time.perf_counter() - started_at) * 1000)
    print(
        f"[api:request] request_id={req_id} method={request.method} "
        f"path={request.url.path} status={response.status_code} duration_ms={duration_ms}"
    )
    response.headers["x-request-id"] = req_id
    return response


@app.exception_handler(HTTPException)
async def structured_http_exception_handler(request: Request, exc: HTTPException):
    req_id = request.headers.get("x-request-id") or request_id()
    return error_envelope_response(
        message=str(exc.detail),
        request_id_value=req_id,
        status_code_value=exc.status_code,
        error_type="HTTPException",
    )


@app.exception_handler(Exception)
async def structured_exception_handler(request: Request, exc: Exception):
    req_id = request.headers.get("x-request-id") or request_id()
    log_exception("unhandled_exception", exc, req_id, path=request.url.path)
    return error_envelope_response(
        message=str(exc),
        request_id_value=req_id,
        status_code_value=500,
        error_type=exc.__class__.__name__,
    )


class DocumentRecord(BaseModel):
    id: str
    user_id: str
    title: str
    file_name: str
    file_key: str
    file_size: int
    mime_type: str
    storage_provider: str
    status: str
    created_at: datetime


class DownloadUrlResponse(BaseModel):
    downloadUrl: str


class AskDocumentRequest(BaseModel):
    question: str


class CompareDocumentsRequest(BaseModel):
    second_document_id: str


class CompassChatRequest(BaseModel):
    message: str
    jurisdiction: str
    conversation_id: str | None = None


class CompassConversationUpdateRequest(BaseModel):
    title: str | None = None
    jurisdiction: str | None = None


class AskSource(BaseModel):
    chunk_index: int
    preview: str


class AskDocumentResponse(BaseModel):
    answer: str
    sources: list[AskSource]


def get_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
      raise HTTPException(
          status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
          detail=f"Server missing required configuration: {name}",
      )
    return value


def get_r2_client():
    endpoint_url = os.getenv("R2_ENDPOINT_URL")
    if not endpoint_url:
        account_id = get_env("R2_ACCOUNT_ID")
        endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=get_env("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=get_env("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


async def get_db_pool():
    pool = getattr(app.state, "db_pool", None)
    if not pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured.",
        )
    return pool


@app.on_event("startup")
async def startup():
    log_openai_startup_config()
    database_url = os.getenv("DATABASE_URL")
    app.state.db_pool = (
        await asyncpg.create_pool(database_url, statement_cache_size=0)
        if database_url
        else None
    )


@app.on_event("shutdown")
async def shutdown():
    pool = getattr(app.state, "db_pool", None)
    if pool:
        await pool.close()


def validate_uploaded_file(file_name: str, reported_content_type: str | None, file_size: int, contents: bytes) -> str:
    extension = os.path.splitext(file_name.lower())[1]
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF, DOC, and DOCX files are supported.")
    if file_size <= 0:
        raise HTTPException(status_code=400, detail="File is empty.")
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds the 25MB limit.")

    if reported_content_type in SUPPORTED_TYPES and SUPPORTED_TYPES[reported_content_type] != extension:
        raise HTTPException(status_code=400, detail="File extension does not match content type.")

    if extension == ".pdf" and not contents.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid PDF.")

    if extension == ".doc" and not contents.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid DOC file.")

    if extension == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(contents)) as archive:
                if "word/document.xml" not in archive.namelist():
                    raise HTTPException(status_code=400, detail="Uploaded file is not a valid DOCX file.")
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=400, detail="Uploaded file is not a valid DOCX file.") from exc

    return EXTENSION_CONTENT_TYPES[extension]


def safe_file_name(file_name: str) -> str:
    base = os.path.basename(file_name).strip()
    name, extension = os.path.splitext(base)
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-._")
    slug = slug[:120] or "document"
    safe_ext = extension.lower() if extension.lower() in SUPPORTED_EXTENSIONS else ""
    return f"{slug}{safe_ext}"


def title_from_file(file_name: str) -> str:
    return os.path.splitext(os.path.basename(file_name))[0].replace("-", " ").replace("_", " ").strip() or "Untitled document"


def bearer_token(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")
    return authorization.removeprefix("Bearer ").strip()


async def current_user_id(token: Annotated[str, Depends(bearer_token)]) -> str:
    supabase_url = get_env("SUPABASE_URL").rstrip("/")
    supabase_api_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server missing required configuration: SUPABASE_ANON_KEY or SUPABASE_SERVICE_ROLE_KEY",
        )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{supabase_url}/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": supabase_api_key,
                },
            )
    except httpx.HTTPError as exc:
        print(f"[supabase:auth] status=unavailable type={exc.__class__.__name__} message={exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not verify auth token with Supabase.",
        ) from exc

    if response.status_code != 200:
        print(
            f"[supabase:auth] status={response.status_code} "
            f"body={sanitize_log_text(response.text, limit=1200)}"
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth token.")

    payload = response.json()
    user_id = payload.get("id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Supabase user response missing user id.")
    return user_id


def user_file_key(user_id: str, document_id: str, file_name: str) -> str:
    return f"users/{user_id}/documents/{document_id}/{safe_file_name(file_name)}"


def document_record(row) -> DocumentRecord:
    return DocumentRecord(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        title=row["title"],
        file_name=row["file_name"],
        file_key=row["file_key"],
        file_size=row["file_size"],
        mime_type=row["mime_type"],
        storage_provider=row["storage_provider"],
        status=row["status"],
        created_at=row["created_at"],
    )


def extract_pdf_text(contents: bytes) -> tuple[str, int]:
    reader = PdfReader(io.BytesIO(contents))
    page_text = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        page_text.append(f"\n\n--- Page {index} ---\n{text.strip()}")

    extracted_text = "\n".join(page_text).strip()
    if not extracted_text:
        raise ValueError("No extractable English text found in PDF.")

    return extracted_text, len(reader.pages)


def chunk_text(text_content: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    normalized = re.sub(r"\s+", " ", text_content).strip()
    if not normalized:
        return []

    chunks = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunks.append(normalized[start:end].strip())
        if end == len(normalized):
            break
        start = max(end - overlap, start + 1)
    return [chunk for chunk in chunks if chunk]


def get_openai_client() -> OpenAI:
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def log_openai_startup_config():
    print(
        "[openai:config] "
        f"openai_key_detected={bool(os.getenv('OPENAI_API_KEY'))} "
        f"chat_model={OPENAI_CHAT_MODEL} "
        f"analysis_model={OPENAI_ANALYSIS_MODEL} "
        f"compass_model={OPENAI_COMPASS_MODEL} "
        f"embedding_model={OPENAI_EMBED_MODEL} "
        f"embedding_dimensions={EMBEDDING_DIMENSIONS}"
    )


def openai_status_code(exc: Exception) -> int | None:
    status_code_value = getattr(exc, "status_code", None)
    if isinstance(status_code_value, int):
        return status_code_value
    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    return response_status if isinstance(response_status, int) else None


def openai_response_body(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    text = getattr(response, "text", None)
    if callable(text):
        try:
            text = text()
        except Exception:
            text = None
    if text:
        return sanitize_log_text(str(text))
    return sanitize_log_text(str(exc))


def openai_error_detail(exc: Exception) -> str:
    body = openai_response_body(exc)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body

    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        message = error.get("message")
        error_type = error.get("type")
        error_code = error.get("code")
        parts = [part for part in [message, error_type, error_code] if part]
        if parts:
            return " | ".join(str(part) for part in parts)
    return body


def openai_error_message(exc: Exception, operation: str, model: str) -> str:
    if isinstance(exc, APIConnectionError):
        return f"OpenAI {operation} connection error for model {model}: {openai_error_detail(exc)}"
    if isinstance(exc, APITimeoutError):
        return f"OpenAI {operation} timed out for model {model}: {openai_error_detail(exc)}"
    if isinstance(exc, APIStatusError):
        return f"OpenAI {operation} failed with HTTP {openai_status_code(exc)} for model {model}: {openai_error_detail(exc)}"
    return f"OpenAI {operation} failed for model {model}: {exc}"


def openai_error_status(exc: Exception) -> int:
    if isinstance(exc, APIConnectionError):
        return 503
    if isinstance(exc, APITimeoutError):
        return 504
    if isinstance(exc, APIStatusError):
        return exc.status_code if exc.status_code in {400, 401, 403, 404, 429} else 502
    return 502


def openai_raw_response(exc: Exception) -> str | None:
    return openai_response_body(exc)


def raise_openai_error(exc: Exception, *, model: str, operation: str):
    status_code_value = openai_status_code(exc)
    error_detail = openai_error_detail(exc)
    raw_response = openai_raw_response(exc)
    print(
        "[openai:error] "
        f"operation={operation} "
        f"model={model} "
        f"type={exc.__class__.__name__} "
        f"http_status={status_code_value} "
        f"message={sanitize_log_text(error_detail, limit=2000)} "
        f"raw_response={sanitize_log_text(raw_response, limit=4000)}"
    )
    raise AIProviderError(
        openai_error_message(exc, operation, model),
        error_type=exc.__class__.__name__,
        model=model,
        status_code=openai_error_status(exc),
        raw_response=raw_response,
    ) from exc


async def generate_embeddings(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    if not texts:
        return []

    embeddings = []

    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[start:start + EMBEDDING_BATCH_SIZE]
        batch_embeddings = await asyncio.to_thread(generate_openai_embeddings_batch, batch)
        if len(batch_embeddings) != len(batch):
            raise RuntimeError("OpenAI embeddings response count did not match chunk count.")
        embeddings.extend(batch_embeddings)

    if len(embeddings) != len(texts):
        raise RuntimeError("OpenAI embeddings response count did not match chunk count.")
    if any(len(embedding) != EMBEDDING_DIMENSIONS for embedding in embeddings):
        raise RuntimeError(
            f"OpenAI embeddings response dimensions did not match the configured "
            f"{EMBEDDING_DIMENSIONS}-dimension document_chunks.embedding. "
            f"Check that OPENAI_EMBED_MODEL is set to {OPENAI_EMBED_MODEL}."
        )
    return embeddings


def generate_openai_embeddings_batch(texts: list[str]) -> list[list[float]]:
    print(
        f"[openai:embed] model={OPENAI_EMBED_MODEL} batch_size={len(texts)} "
        f"dimensions={EMBEDDING_DIMENSIONS}"
    )
    try:
        response = get_openai_client().embeddings.create(
            model=OPENAI_EMBED_MODEL,
            input=texts,
        )
    except OpenAIError as exc:
        raise_openai_error(exc, model=OPENAI_EMBED_MODEL, operation="embedding")

    embeddings = [item.embedding for item in response.data]
    normalized_embeddings = [normalize_embedding(embedding) for embedding in embeddings]
    print(f"[openai:embed] model={OPENAI_EMBED_MODEL} returned={len(normalized_embeddings)}")
    return normalized_embeddings


async def generate_answer(prompt: str) -> str:
    return await generate_text(prompt, max_output_tokens=700, model=OPENAI_CHAT_MODEL)


async def generate_summary(prompt: str) -> str:
    return await generate_text(prompt, max_output_tokens=3200, model=OPENAI_ANALYSIS_MODEL)


async def generate_clauses(prompt: str) -> dict:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(generate_openai_json, prompt, 5200, OPENAI_ANALYSIS_MODEL),
            timeout=AI_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise AIProviderError(
            f"OpenAI clause intelligence request timed out after {AI_TIMEOUT_SECONDS} seconds.",
            error_type="TimeoutError",
            model=OPENAI_ANALYSIS_MODEL,
            status_code=504,
        ) from exc


async def generate_risk_analysis(prompt: str) -> dict:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(generate_openai_json, prompt, 5200, OPENAI_ANALYSIS_MODEL),
            timeout=AI_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise AIProviderError(
            f"OpenAI risk analysis request timed out after {AI_TIMEOUT_SECONDS} seconds.",
            error_type="TimeoutError",
            model=OPENAI_ANALYSIS_MODEL,
            status_code=504,
        ) from exc


async def generate_document_compare(prompt: str) -> dict:
    last_empty_response = None
    for attempt in range(2):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    generate_openai_json,
                    prompt,
                    COMPARE_MAX_OUTPUT_TOKENS,
                    OPENAI_ANALYSIS_MODEL,
                    COMPARE_TIMEOUT_SECONDS,
                ),
                timeout=COMPARE_TIMEOUT_SECONDS,
            )
        except AIProviderError as exc:
            if exc.error_type == "EmptyOpenAIResponse" and attempt == 0:
                last_empty_response = exc
                print(
                    f"[ai:compare:retry] reason=empty_response "
                    f"attempt={attempt + 1} model={OPENAI_ANALYSIS_MODEL}"
                )
                continue
            if exc.error_type in {"EmptyOpenAIResponse", "APITimeoutError", "TimeoutError"}:
                raise AIProviderError(
                    "Compare took too long or returned no output. Try again with shorter documents.",
                    error_type=exc.error_type,
                    model=exc.model or OPENAI_ANALYSIS_MODEL,
                    status_code=504,
                    raw_response=exc.raw_response,
                ) from exc
            raise
        except asyncio.TimeoutError as exc:
            raise AIProviderError(
                "Compare took too long or returned no output. Try again with shorter documents.",
                error_type="TimeoutError",
                model=OPENAI_ANALYSIS_MODEL,
                status_code=504,
            ) from exc

    raise AIProviderError(
        "Compare took too long or returned no output. Try again with shorter documents.",
        error_type="EmptyOpenAIResponse",
        model=OPENAI_ANALYSIS_MODEL,
        status_code=504,
        raw_response=last_empty_response.raw_response if last_empty_response else "",
    )


async def generate_intelligence(prompt: str) -> dict:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(generate_openai_json, prompt, 5200, OPENAI_ANALYSIS_MODEL),
            timeout=AI_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise AIProviderError(
            f"OpenAI intelligence request timed out after {AI_TIMEOUT_SECONDS} seconds.",
            error_type="TimeoutError",
            status_code=504,
        ) from exc


async def generate_text(prompt: str, max_output_tokens: int, model: str) -> str:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(generate_openai_text, prompt, max_output_tokens, model),
            timeout=AI_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise AIProviderError(
            f"OpenAI text request timed out after {AI_TIMEOUT_SECONDS} seconds.",
            error_type="TimeoutError",
            status_code=504,
        ) from exc


def generate_openai_text(prompt: str, max_output_tokens: int, model: str) -> str:
    print(f"[openai:text] model={model} max_output_tokens={max_output_tokens}")
    try:
        response = get_openai_client().chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=max_output_tokens,
        )
    except OpenAIError as exc:
        raise_openai_error(exc, model=model, operation="text generation")

    answer = (response.choices[0].message.content or "").strip() if response.choices else ""
    print(f"[openai:text] model={model} response_chars={len(answer)}")
    return answer


def generate_openai_json(
    prompt: str,
    max_output_tokens: int,
    model: str,
    timeout_seconds: int | None = None,
) -> dict:
    print(
        f"[openai:json] model={model} max_output_tokens={max_output_tokens} "
        f"prompt_chars={len(prompt)} timeout_seconds={timeout_seconds or AI_TIMEOUT_SECONDS}"
    )
    try:
        response = get_openai_client().chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=max_output_tokens,
            response_format={"type": "json_object"},
        )
    except OpenAIError as exc:
        raise_openai_error(exc, model=model, operation="JSON generation")

    text = (response.choices[0].message.content or "").strip() if response.choices else ""
    print(f"[openai:json] model={model} response_chars={len(text)}")
    if not text:
        raise AIProviderError(
            "OpenAI returned an empty JSON response.",
            error_type="EmptyOpenAIResponse",
            model=model,
            status_code=502,
        )

    try:
        return parse_json_response(text)
    except Exception as exc:
        print(f"[openai:json:parse_error] raw_response={sanitize_log_text(text)}")
        raise AIProviderError(
            "OpenAI returned invalid JSON.",
            error_type="JSONParseError",
            model=model,
            status_code=502,
            raw_response=text,
        ) from exc


def parse_json_response(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise RuntimeError("AI provider did not return valid JSON.") from exc
        data = json.loads(match.group(0))

    if not isinstance(data, dict):
        raise RuntimeError("AI provider intelligence response must be a JSON object.")
    return data


def normalize_compass_jurisdiction(value: str | None) -> str:
    candidate = str(value or "").strip()
    for jurisdiction in COMPASS_JURISDICTIONS:
        if candidate.casefold() == jurisdiction.casefold():
            return jurisdiction
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported jurisdiction. Choose one of: {', '.join(COMPASS_JURISDICTIONS)}.",
    )


def normalize_compass_conversation_id(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid Compass conversation id.") from exc


def compass_conversation_title(message: str) -> str:
    title = re.sub(r"\s+", " ", message).strip().rstrip("?.!")
    return (title[:76].rstrip() or "New legal research")


def build_compass_system_prompt(jurisdiction: str, checked_at: str) -> str:
    return f"""You are Juris Compass, a legal information and legal research system.

You explain laws, Acts, statutes, regulations, procedures, doctrines, rights, obligations, and legal concepts. You are completely independent from Juris document intelligence. You have no uploaded document, no PDF chunks, no document embeddings, and no private document context.

JURISDICTION: {jurisdiction}
CHECKED AS OF: {checked_at}

Research rules:
- Use web search before answering and prioritize current primary legal authorities.
- Prefer official legislation sites, government portals, gazettes, official courts, and regulators.
- Never invent a statute, section, case, quotation, or source.
- Separate confirmed law from interpretation and state uncertainty honestly.
- If the selected jurisdiction is Other and the question does not identify a jurisdiction, ask one concise clarification question instead of assuming.
- Explain complex legal language simply.
- Do not provide personalized legal advice or predict a user's legal outcome.
- For high-risk personal matters, recommend advice from a qualified legal professional.
- Keep the answer useful and concise.

Return plain text with exactly these headings, each on its own line:
DIRECT ANSWER
PLAIN ENGLISH
LEGAL BASIS
IMPORTANT EXCEPTIONS
PRACTICAL NOTES
AUTHORITATIVE SOURCES

Under AUTHORITATIVE SOURCES, name only the authorities actually consulted. The application will attach the verified clickable URLs separately."""


def parse_compass_sections(answer: str) -> dict:
    heading_map = {
        "DIRECT ANSWER": "directAnswer",
        "PLAIN ENGLISH": "plainEnglish",
        "LEGAL BASIS": "legalBasis",
        "IMPORTANT EXCEPTIONS": "importantExceptions",
        "EXCEPTIONS": "importantExceptions",
        "PRACTICAL NOTES": "practicalNotes",
        "AUTHORITATIVE SOURCES": "authoritativeSources",
        "SOURCES": "authoritativeSources",
    }
    sections = {value: "" for value in set(heading_map.values())}
    active_key = None

    for raw_line in answer.splitlines():
        line = raw_line.strip()
        normalized = re.sub(r"^[#*\s]+|[:\s]+$", "", line).upper()
        if normalized in heading_map:
            active_key = heading_map[normalized]
            continue
        if active_key and line:
            sections[active_key] = f"{sections[active_key]}\n{line}".strip()

    if not any(sections.values()):
        sections["directAnswer"] = answer.strip()
    return sections


def extract_compass_sources(response) -> list[dict]:
    payload = response.model_dump() if hasattr(response, "model_dump") else response
    found = []
    seen = set()

    def add_source(url, title=None):
        if not isinstance(url, str) or not url.startswith(("http://", "https://")) or url in seen:
            return
        seen.add(url)
        host = urlparse(url).netloc.removeprefix("www.")
        found.append({
            "title": str(title or host or "Legal source"),
            "url": url,
            "domain": host,
        })

    def walk(value):
        if isinstance(value, dict):
            citation = value.get("url_citation")
            if isinstance(citation, dict):
                add_source(citation.get("url"), citation.get("title"))
            if value.get("type") == "url_citation":
                add_source(value.get("url"), value.get("title"))
            if "url" in value and ("title" in value or value.get("type") in {"source", "url"}):
                add_source(value.get("url"), value.get("title"))
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    return found[:12]


def generate_openai_compass(
    *,
    jurisdiction: str,
    message: str,
    history: list[dict],
    checked_at: str,
) -> dict:
    web_search_tool = {
        "type": "web_search",
        "search_context_size": "low",
    }
    allowed_domains = COMPASS_SOURCE_DOMAINS.get(jurisdiction)
    if allowed_domains:
        web_search_tool["filters"] = {"allowed_domains": allowed_domains}

    input_messages = [
        {"role": item["role"], "content": item["content"]}
        for item in history[-COMPASS_HISTORY_LIMIT:]
        if item.get("role") in {"user", "assistant"} and item.get("content")
    ]
    input_messages.append({"role": "user", "content": message})

    print(
        f"[openai:compass] model={OPENAI_COMPASS_MODEL} jurisdiction={jurisdiction} "
        f"history_messages={len(input_messages) - 1} message_chars={len(message)}"
    )
    try:
        response = get_openai_client().responses.create(
            model=OPENAI_COMPASS_MODEL,
            instructions=build_compass_system_prompt(jurisdiction, checked_at),
            input=input_messages,
            tools=[web_search_tool],
            tool_choice="auto",
            include=["web_search_call.action.sources"],
            max_tool_calls=2,
            max_output_tokens=COMPASS_MAX_OUTPUT_TOKENS,
            reasoning={"effort": "low"},
        )
    except OpenAIError as exc:
        raise_openai_error(exc, model=OPENAI_COMPASS_MODEL, operation="Compass legal research")

    answer = str(getattr(response, "output_text", "") or "").strip()
    if not answer:
        response_status = str(getattr(response, "status", "unknown") or "unknown")
        incomplete_details = getattr(response, "incomplete_details", None)
        incomplete_reason = str(getattr(incomplete_details, "reason", "") or "")
        raise AIProviderError(
            "Juris Compass reached its research limit before producing an answer. Please try a narrower question."
            if incomplete_reason == "max_output_tokens"
            else "Juris Compass returned no legal research output.",
            error_type="EmptyOpenAIResponse",
            model=OPENAI_COMPASS_MODEL,
            status_code=502,
            raw_response=f"status={response_status}; incomplete_reason={incomplete_reason or 'not provided'}",
        )

    sources = extract_compass_sources(response)
    sections = parse_compass_sections(answer)
    print(
        f"[openai:compass] model={OPENAI_COMPASS_MODEL} response_chars={len(answer)} "
        f"sources={len(sources)}"
    )
    return {
        "answer": answer,
        "sections": sections,
        "jurisdiction": jurisdiction,
        "checkedAt": checked_at,
        "legalBasis": sections.get("legalBasis") or "Not confirmed in the returned sources.",
        "sources": sources,
        "sourceType": "Verified law" if sources else "Source verification unavailable",
        "verificationStatus": "Verified sources attached" if sources else "No verified sources returned",
        "disclaimer": COMPASS_DISCLAIMER,
    }


async def generate_compass_research(
    *,
    jurisdiction: str,
    message: str,
    history: list[dict],
    checked_at: str,
) -> dict:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(
                generate_openai_compass,
                jurisdiction=jurisdiction,
                message=message,
                history=history,
                checked_at=checked_at,
            ),
            timeout=AI_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise AIProviderError(
            f"Juris Compass timed out after {AI_TIMEOUT_SECONDS} seconds while checking legal sources.",
            error_type="TimeoutError",
            model=OPENAI_COMPASS_MODEL,
            status_code=504,
        ) from exc


def decode_compass_json(value) -> dict | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None
    return None


def compass_conversation_payload(row) -> dict:
    data = dict(row)
    return {
        "id": str(data["id"]),
        "title": data["title"],
        "jurisdiction": data["jurisdiction"],
        "messageCount": int(data.get("message_count") or 0),
        "preview": data.get("preview") or "No research yet.",
        "createdAt": data["created_at"],
        "updatedAt": data["updated_at"],
    }


def compass_message_payload(row) -> dict:
    data = dict(row)
    return {
        "id": str(data["id"]),
        "role": data["role"],
        "content": data["content"],
        "data": decode_compass_json(data.get("response_json")),
        "createdAt": data["created_at"],
    }


def normalize_intelligence_payload(payload: dict) -> dict:
    normalized = {
        "documentType": "Not specified",
        "confidence": "Not specified",
        "snapshot": {},
        "plainEnglishSummary": "Not specified",
        "keyInformation": {},
        "timeline": [],
        "financialSummary": {},
        "obligations": {"partyA": [], "partyB": []},
        "keyClauses": [],
        "riskHighlights": [],
        "missingInformation": [],
        "recommendedQuestions": [],
    }

    for key in normalized:
        if key in payload:
            normalized[key] = payload[key]

    if not isinstance(normalized["snapshot"], dict):
        normalized["snapshot"] = {}
    if not isinstance(normalized["keyInformation"], dict):
        normalized["keyInformation"] = {}
    if not isinstance(normalized["financialSummary"], dict):
        normalized["financialSummary"] = {}
    if not isinstance(normalized["obligations"], dict):
        normalized["obligations"] = {"partyA": [], "partyB": []}

    for key in ("timeline", "keyClauses", "riskHighlights", "missingInformation", "recommendedQuestions"):
        value = normalized[key]
        if isinstance(value, str):
            normalized[key] = [value] if value else []
        elif not isinstance(value, list):
            normalized[key] = []

    confidence = normalize_confidence_percentage(
        normalized.get("confidence") or normalized["snapshot"].get("estimatedAiConfidence")
    )
    normalized["confidence"] = confidence
    normalized["snapshot"]["estimatedAiConfidence"] = confidence

    return normalized


def normalize_clauses_payload(payload: dict) -> dict:
    raw_clauses = payload.get("clauses") if isinstance(payload, dict) else []
    if not isinstance(raw_clauses, list):
        raw_clauses = []

    return {
        "documentType": display_payload_text(payload.get("documentType")) if isinstance(payload, dict) else "Not specified",
        "clauses": [normalize_clause_item(item) for item in raw_clauses if isinstance(item, dict)],
    }


def normalize_clause_item(item: dict) -> dict:
    return {
        "title": display_payload_text(item.get("title")),
        "category": display_payload_text(item.get("category")),
        "plainEnglish": display_payload_text(item.get("plainEnglish")),
        "whyItMatters": display_payload_text(item.get("whyItMatters")),
        "riskLevel": normalize_risk_level(item.get("riskLevel")),
        "importantTerms": normalize_payload_list(item.get("importantTerms")),
        "obligations": normalize_party_action_list(item.get("obligations"), "obligation"),
        "rights": normalize_party_action_list(item.get("rights"), "right"),
        "restrictions": normalize_payload_list(item.get("restrictions")),
        "deadlines": normalize_payload_list(item.get("deadlines")),
        "financialTerms": normalize_payload_list(item.get("financialTerms")),
        "sourceReference": display_payload_text(item.get("sourceReference")),
        "confidence": normalize_confidence_number(item.get("confidence")),
    }


def normalize_risk_analysis_payload(payload: dict) -> dict:
    raw_risks = payload.get("risks") if isinstance(payload, dict) else []
    if not isinstance(raw_risks, list):
        raw_risks = []

    return {
        "documentType": display_payload_text(payload.get("documentType")) if isinstance(payload, dict) else "Not specified",
        "overallRisk": normalize_risk_level(payload.get("overallRisk")) if isinstance(payload, dict) else "Low",
        "summary": display_payload_text(payload.get("summary")) if isinstance(payload, dict) else "Not specified",
        "risks": [normalize_risk_item(item) for item in raw_risks if isinstance(item, dict)],
        "missingProtections": normalize_payload_list(payload.get("missingProtections") if isinstance(payload, dict) else []),
        "unusualTerms": normalize_payload_list(payload.get("unusualTerms") if isinstance(payload, dict) else []),
        "financialRisks": normalize_payload_list(payload.get("financialRisks") if isinstance(payload, dict) else []),
        "legalRisks": normalize_payload_list(payload.get("legalRisks") if isinstance(payload, dict) else []),
        "complianceRisks": normalize_payload_list(payload.get("complianceRisks") if isinstance(payload, dict) else []),
    }


def normalize_risk_item(item: dict) -> dict:
    return {
        "title": display_payload_text(item.get("title")),
        "category": display_payload_text(item.get("category")),
        "severity": normalize_risk_level(item.get("severity")),
        "description": display_payload_text(item.get("description")),
        "whyItMatters": display_payload_text(item.get("whyItMatters")),
        "recommendation": display_payload_text(item.get("recommendation")),
        "affectedParty": display_payload_text(item.get("affectedParty")),
        "sourceReference": display_payload_text(item.get("sourceReference")),
        "confidence": normalize_confidence_number(item.get("confidence")),
    }


def normalize_compare_payload(payload: dict, document_a, document_b) -> dict:
    raw_differences = payload.get("differences") if isinstance(payload, dict) else []
    if not isinstance(raw_differences, list):
        raw_differences = []

    document_a_payload = payload.get("documentA") if isinstance(payload, dict) and isinstance(payload.get("documentA"), dict) else {}
    document_b_payload = payload.get("documentB") if isinstance(payload, dict) and isinstance(payload.get("documentB"), dict) else {}

    return {
        "documentA": normalize_compare_document(document_a, document_a_payload),
        "documentB": normalize_compare_document(document_b, document_b_payload),
        "areComparable": normalize_boolean(payload.get("areComparable")) if isinstance(payload, dict) else False,
        "summary": display_payload_text(payload.get("summary")) if isinstance(payload, dict) else "Not specified",
        "differences": [normalize_compare_difference(item) for item in raw_differences if isinstance(item, dict)][:8],
        "financialDifferences": normalize_payload_list(payload.get("financialDifferences") if isinstance(payload, dict) else [])[:8],
        "obligationDifferences": normalize_payload_list(payload.get("obligationDifferences") if isinstance(payload, dict) else [])[:8],
        "deadlineDifferences": normalize_payload_list(payload.get("deadlineDifferences") if isinstance(payload, dict) else [])[:8],
        "riskDifferences": normalize_payload_list(payload.get("riskDifferences") if isinstance(payload, dict) else [])[:8],
        "recommendedQuestions": normalize_payload_list(payload.get("recommendedQuestions") if isinstance(payload, dict) else [])[:5],
    }


def normalize_compare_document(document, payload: dict) -> dict:
    return {
        "id": str(document["id"]),
        "name": display_payload_text(document["file_name"] or document["title"]),
        "documentType": display_payload_text(payload.get("documentType")),
    }


def normalize_compare_difference(item: dict) -> dict:
    return {
        "title": display_payload_text(item.get("title")),
        "type": normalize_difference_type(item.get("type")),
        "category": display_payload_text(item.get("category")),
        "documentA": display_payload_text(item.get("documentA")),
        "documentB": display_payload_text(item.get("documentB")),
        "impact": display_payload_text(item.get("impact")),
        "riskChange": normalize_risk_change(item.get("riskChange")),
        "affectedParty": display_payload_text(item.get("affectedParty")),
        "sourceReference": display_payload_text(item.get("sourceReference")),
        "confidence": normalize_confidence_number(item.get("confidence")),
    }


def normalize_boolean(value) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    return normalized in {"true", "yes", "comparable", "1"}


def normalize_difference_type(value) -> str:
    normalized = str(value or "").strip().lower()
    allowed = {
        "added": "Added",
        "removed": "Removed",
        "changed": "Changed",
        "same": "Same",
    }
    return allowed.get(normalized, "Changed")


def normalize_risk_change(value) -> str:
    normalized = str(value or "").strip().lower()
    allowed = {
        "lower": "Lower",
        "same": "Same",
        "higher": "Higher",
        "not applicable": "Not applicable",
        "n/a": "Not applicable",
        "na": "Not applicable",
    }
    return allowed.get(normalized, "Not applicable")


def jsonable(value):
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, (datetime, uuid.UUID)):
        return str(value)
    return value


def stable_json(value) -> str:
    return json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def build_input_hash(payload: dict) -> str:
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def chunk_content_hash(chunks) -> str:
    parts = [
        {
            "index": row["chunk_index"],
            "text": row["chunk_text"],
        }
        for row in chunks
    ]
    return build_input_hash({"chunks": parts})


def decode_ai_output(value) -> dict:
    if isinstance(value, str):
        return json.loads(value)
    if isinstance(value, dict):
        return value
    return {}


def display_payload_text(value) -> str:
    if value is None:
        return "Not specified"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True)
    normalized = str(value).strip()
    return normalized or "Not specified"


def normalize_risk_level(value) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"low", "medium", "high"}:
        return normalized.title()
    return "Low"


def normalize_payload_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [
            display_payload_text(item)
            for item in value
            if has_payload_value(item) and not is_payload_not_applicable(item)
        ]
    if has_payload_value(value) and not is_payload_not_applicable(value):
        return [display_payload_text(value)]
    return []


def normalize_party_action_list(value, action_key: str) -> list[dict]:
    if not isinstance(value, list):
        return []

    normalized = []
    for item in value:
        if isinstance(item, dict):
            party = display_payload_text(item.get("party"))
            action = display_payload_text(item.get(action_key))
        else:
            party = "Not specified"
            action = display_payload_text(item)
        if action and not is_payload_not_applicable(action):
            normalized.append({"party": party, action_key: action})
    return normalized


def normalize_confidence_number(value) -> int:
    if isinstance(value, (int, float)):
        number = value * 100 if 0 <= value <= 1 else value
        return round(max(0, min(100, number)))
    match = re.search(r"(\d+(?:\.\d+)?)", str(value or ""))
    if not match:
        return 0
    number = float(match.group(1))
    if number <= 1 and "%" not in str(value):
        number *= 100
    return round(max(0, min(100, number)))


def has_payload_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, list):
        return any(has_payload_value(item) for item in value)
    if isinstance(value, dict):
        return any(has_payload_value(item) for item in value.values())
    return bool(str(value).strip())


def is_payload_not_applicable(value) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized in {"not applicable", "not specified", "none", "n/a"}


def normalize_confidence_percentage(value) -> str:
    if value is None:
        return "Not specified"

    if isinstance(value, (int, float)):
        percentage = value * 100 if 0 <= value <= 1 else value
        return f"{round(max(0, min(100, percentage)))}%"

    normalized = str(value).strip().lower()
    if not normalized:
        return "Not specified"

    confidence_map = {
        "high": "90%",
        "medium": "70%",
        "low": "45%",
    }
    if normalized in confidence_map:
        return confidence_map[normalized]

    match = re.search(r"(\d+(?:\.\d+)?)", normalized)
    if match:
        number = float(match.group(1))
        if number <= 1 and "%" not in normalized:
            number *= 100
        return f"{round(max(0, min(100, number)))}%"

    return "Not specified"


def normalize_embedding(embedding: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in embedding))
    if magnitude == 0:
        return embedding
    return [value / magnitude for value in embedding]


def vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(str(value) for value in embedding) + "]"


def chunk_preview(text: str, limit: int = 220) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit].rstrip()}..."


def build_document_answer_prompt(question: str, chunks) -> str:
    chunk_blocks = "\n\n".join(
        f"[Chunk {row['chunk_index']}]\n{row['chunk_text']}"
        for row in chunks
    )
    return f"""
You are Juris, an AI legal document assistant.

Answer the user's question using only the document chunks below.
Do not use outside knowledge.
Do not hallucinate or infer facts that are not present in the chunks.
If the answer is not found in the chunks, say exactly:
"I could not find that information in this document."
Keep the answer clear and simple.
Mention the chunk numbers used when possible.

Document chunks:
{chunk_blocks}

Question:
{question}
""".strip()


def build_document_summary_prompt(chunks) -> str:
    chunk_blocks = "\n\n".join(
        f"[Chunk {row['chunk_index']}]\n{row['chunk_text']}"
        for row in chunks
    )
    return f"""
You are a legal document analyst.
Analyze the uploaded English legal document.
First identify the document type.
Then create a concise executive summary that adapts to the document type.

Return only Markdown.

Use these headings exactly as Markdown headings:
## Executive Summary
## Document Type
## Parties Involved
## Purpose of the Document
## Key Terms
## Important Dates
## Payment / Financial Terms
## Obligations of Each Party
## Rights of Each Party
## Termination / Expiry
## Confidentiality / Restrictions
## Dispute Resolution / Governing Law
## Risks or Unusual Terms
## Missing or Not Specified Information

Rules:
- Use only information found in the document.
- Do not invent missing details.
- If a section does not apply, write "Not applicable."
- If information is not present, write "Not specified."
- Keep language simple and clear.
- Do not assume this is a rental agreement.
- Adapt the analysis to NDAs, contracts, leases, employment agreements, service agreements, and other legal documents.

Document chunks in order:
{chunk_blocks}
""".strip()


def build_document_intelligence_prompt(chunks, page_count: int | None) -> str:
    chunk_blocks = "\n\n".join(
        f"[Chunk {row['chunk_index']}]\n{row['chunk_text']}"
        for row in chunks
    )
    known_pages = page_count if page_count else "Not specified"
    return f"""
You are a legal document analyst for Juris.

Analyze the uploaded English legal document and produce structured legal intelligence.
Your goal is to answer: "What should I care about in this document?"

Important:
- First identify the document type. Never assume it is a rental agreement.
- Adapt automatically to rental agreements, NDAs, employment agreements, service agreements, vendor contracts, partnership agreements, loan agreements, policies, terms and conditions, and any other English legal document.
- Use only information supported by the document chunks.
- Never hallucinate.
- Never invent missing details.
- If a value is unavailable, use "Not specified".
- Return only valid JSON. Do not include Markdown, explanations, or code fences.
- Keep text concise and dashboard-friendly.

Known metadata:
- Number of pages: {known_pages}

Return this exact top-level JSON shape:
{{
  "documentType": "",
  "confidence": "92%",
  "snapshot": {{}},
  "plainEnglishSummary": "",
  "keyInformation": {{}},
  "timeline": [],
  "financialSummary": {{}},
  "obligations": {{
    "partyA": [],
    "partyB": []
  }},
  "keyClauses": [],
  "riskHighlights": [],
  "missingInformation": [],
  "recommendedQuestions": []
}}

Section requirements:

1. Executive Snapshot
Set "snapshot" with:
- documentType
- estimatedAiConfidence as a numeric percentage string only, such as "92%". Do not use High, Medium, or Low.
- numberOfParties
- numberOfPages
- numberOfMajorClauses
- estimatedRiskCount

2. Plain-English Summary
Set "plainEnglishSummary" to under 120 words.
Answer: "If I only have 30 seconds, what should I know?"

3. Key Information
Set "keyInformation" to an object.
Extract only fields supported by the document, such as:
- parties
- propertyOrSubject
- effectiveDate
- expiration
- governingLaw
- jurisdiction
- noticePeriod
Do not include absent fields unless the document explicitly expects the field and leaves it blank.

4. Timeline
Set "timeline" to chronological items.
Each item should be an object with "label", "date", and "detail".
Examples: Agreement Starts, Payment Due, Renewal, Termination, Expiry.
If unavailable, return [].

5. Financial Summary
Set "financialSummary" to an object containing supported financial terms, such as:
- payments
- deposits
- salary
- fees
- penalties
- interest
- refunds
Adapt to the document type. If no financial terms are present, use {{ "status": "Not specified" }}.

6. Obligations Matrix
Set "obligations" to an object split by parties or roles.
Use actual party names or roles as keys when they are clear, such as Landlord, Tenant, Company, Employee, Client, Vendor, Partner A, Partner B.
If parties are unclear, use "partyA" and "partyB".
Each party value must be an array of short obligation strings.

7. Key Clauses
Set "keyClauses" to an array of clause titles only.
Examples: Termination, Confidentiality, Liability, Indemnity, Force Majeure, Payment, Renewal, Arbitration, IP Ownership, Non-compete.
Do not explain these clauses here.

8. Risk Highlights
Set "riskHighlights" to an array of important legal risks.
Examples: Automatic Renewal, High Penalty, Unlimited Liability, One-sided Termination, Broad Confidentiality, Missing Payment Terms, Missing Termination, Missing Governing Law.
If no major risks are detected, return ["No major risks detected."].

9. Missing Information
Set "missingInformation" to an array of important expected legal information that appears absent.
Examples: Missing signatures, Missing expiry, Missing governing law, Missing witnesses, Missing notice period.
If nothing important appears missing, return [].

10. Recommended Questions
Set "recommendedQuestions" to exactly 5 useful questions for Chat.
Examples:
- What are my payment obligations?
- Can this agreement be terminated early?
- Who owns the intellectual property?
- What happens if either party breaches?
- Are there any unusual clauses?

Document chunks in order:
{chunk_blocks}
""".strip()


def build_document_clauses_prompt(chunks) -> str:
    chunk_blocks = "\n\n".join(
        f"[Chunk {row['chunk_index']}]\n{row['chunk_text']}"
        for row in chunks
    )
    return f"""
You are a legal document analyst for Juris.

Analyze the uploaded English legal document and extract the important clauses.
First identify the document type. Never assume it is a rental agreement.
Adapt clause extraction to the actual document type, including rental agreements, NDAs, employment agreements, service agreements, vendor contracts, partnership agreements, loan agreements, terms and conditions, privacy policies, and any other English legal document.

Important rules:
- Use only information supported by the document chunks.
- Do not invent clauses.
- If a clause is not found, do not include it.
- Do not use landlord/tenant language unless the document is actually a lease or rental agreement.
- If a field is not applicable, use an empty array or "Not applicable".
- Explain legal language in simple English.
- Highlight why each clause matters.
- Assign riskLevel based on legal/business impact, not fear.
- Include sourceReference using chunk numbers where possible, such as "Chunk 3" or "Chunks 2, 4".
- Return only valid JSON. Do not include Markdown, explanations, or code fences.

Return this exact top-level JSON shape:
{{
  "documentType": "",
  "clauses": [
    {{
      "title": "",
      "category": "",
      "plainEnglish": "",
      "whyItMatters": "",
      "riskLevel": "Low",
      "importantTerms": [],
      "obligations": [
        {{
          "party": "",
          "obligation": ""
        }}
      ],
      "rights": [
        {{
          "party": "",
          "right": ""
        }}
      ],
      "restrictions": [],
      "deadlines": [],
      "financialTerms": [],
      "sourceReference": "",
      "confidence": 0
    }}
  ]
}}

Field guidance:
- "title": concise clause title found or strongly supported by headings/text.
- "category": legal category, such as Termination, Confidentiality, Payment, Liability, IP Ownership, Privacy, Dispute Resolution, Employment, Data Use, Renewal, Breach, Indemnity, Governing Law, or another document-appropriate category.
- "plainEnglish": what the clause means in simple English.
- "whyItMatters": why a reader should care about it.
- "riskLevel": exactly one of "Low", "Medium", or "High".
- "importantTerms": key defined terms, thresholds, conditions, exceptions, standards, or requirements.
- "obligations": party-specific duties only.
- "rights": party-specific rights only.
- "restrictions": prohibitions or limits.
- "deadlines": dates, notice periods, renewal windows, payment dates, response periods, or expiry periods.
- "financialTerms": payments, fees, penalties, deposits, salary, interest, refunds, reimbursements, or other money terms.
- "sourceReference": chunk reference that supports the clause, such as "Chunk 2" or "Chunks 1, 3".
- "confidence": integer from 0 to 100 based on how clearly the clause is supported by the chunks.

Document chunks in order:
{chunk_blocks}
""".strip()


def build_document_risk_analysis_prompt(chunks) -> str:
    chunk_blocks = "\n\n".join(
        f"[Chunk {row['chunk_index']}]\n{row['chunk_text']}"
        for row in chunks
    )
    return f"""
You are a legal document risk analyst for Juris.

Analyze the uploaded English legal document for legal, financial, operational, and compliance risks.
First identify the document type. Never assume it is a rental agreement.
Adapt the risk analysis to the actual document type, including rental agreements, employment agreements, NDAs, loan agreements, vendor contracts, service agreements, partnership agreements, purchase agreements, terms and conditions, privacy policies, and any other English legal document.

Important rules:
- Use only information supported by the document chunks.
- Never invent risks.
- Do not report generic risks unless the document text supports them.
- If no risks are found, set "risks" to [] and explain that in "summary".
- Explain every risk in plain English.
- Include a practical recommendation for every risk.
- Assign severity based on legal impact, financial exposure, operational burden, compliance exposure, or imbalance between parties.
- Include sourceReference using chunk numbers where possible, such as "Chunk 3" or "Chunks 2, 4".
- Do not assume document type.
- Return only valid JSON. Do not include Markdown, explanations, or code fences.

Return this exact top-level JSON shape:
{{
  "documentType": "",
  "overallRisk": "Low",
  "summary": "",
  "risks": [
    {{
      "title": "",
      "category": "",
      "severity": "Low",
      "description": "",
      "whyItMatters": "",
      "recommendation": "",
      "affectedParty": "",
      "sourceReference": "",
      "confidence": 0
    }}
  ],
  "missingProtections": [],
  "unusualTerms": [],
  "financialRisks": [],
  "legalRisks": [],
  "complianceRisks": []
}}

Field guidance:
- "documentType": the best supported document type from the text.
- "overallRisk": exactly one of "Low", "Medium", or "High".
- "summary": short plain-English overview of the document's risk posture.
- "risks": concrete risk items supported by the chunks. If no risks are found, return [].
- "title": concise risk name.
- "category": risk category, such as Legal, Financial, Operational, Compliance, Privacy, Employment, IP, Liability, Termination, Payment, Renewal, Confidentiality, Data Use, Dispute Resolution, or another document-appropriate category.
- "severity": exactly one of "Low", "Medium", or "High".
- "description": what the risky term or missing protection says in simple English.
- "whyItMatters": why this could affect the user or a party.
- "recommendation": practical review or negotiation step.
- "affectedParty": the party, role, or user most affected. Use "Not specified" if unclear.
- "sourceReference": chunk reference that supports the risk, such as "Chunk 2" or "Chunks 1, 3".
- "confidence": integer from 0 to 100 based on how clearly the risk is supported by the chunks.
- "missingProtections": important protective terms commonly expected for this document type that appear absent. Only include absent protections when absence is supported by the document context.
- "unusualTerms": unusual or one-sided supported terms.
- "financialRisks": payment, fee, deposit, penalty, interest, refund, salary, damages, or cost risks.
- "legalRisks": liability, termination, governing law, dispute, indemnity, IP, confidentiality, employment, enforceability, or rights risks.
- "complianceRisks": privacy, data protection, regulatory, reporting, consent, notice, policy, workplace, or statutory compliance risks.

Document chunks in order:
{chunk_blocks}
""".strip()


COMPARE_IMPORTANT_TERMS = (
    "termination",
    "terminate",
    "expiry",
    "expiration",
    "renewal",
    "payment",
    "fee",
    "fees",
    "deposit",
    "penalty",
    "interest",
    "salary",
    "refund",
    "liability",
    "indemn",
    "confidential",
    "privacy",
    "data",
    "intellectual property",
    "ip ownership",
    "warranty",
    "breach",
    "default",
    "notice",
    "governing law",
    "jurisdiction",
    "dispute",
    "arbitration",
    "obligation",
    "responsibility",
    "right",
    "restriction",
    "non-compete",
    "non-solicit",
    "assignment",
    "force majeure",
    "compliance",
    "consent",
)


def select_compare_chunks(
    chunks,
    *,
    char_budget: int = COMPARE_CONTEXT_CHAR_BUDGET,
    max_chunks: int = COMPARE_MAX_CHUNKS_PER_DOCUMENT,
) -> list:
    if not chunks:
        return []

    scored_chunks = []
    for position, row in enumerate(chunks):
        text = row["chunk_text"] or ""
        score = compare_chunk_score(text)
        if position == 0:
            score += 8
        if position == len(chunks) - 1:
            score += 3
        scored_chunks.append((score, position, row))

    selected = []
    total_chars = 0
    for _, _, row in sorted(scored_chunks, key=lambda item: (-item[0], item[1])):
        text_length = len(row["chunk_text"] or "")
        if len(selected) >= max_chunks:
            break
        if selected and total_chars + text_length > char_budget:
            continue
        selected.append(row)
        total_chars += text_length

    return sorted(selected, key=lambda row: row["chunk_index"])


def compare_chunk_score(text: str) -> int:
    normalized = text.lower()
    return sum(normalized.count(term) for term in COMPARE_IMPORTANT_TERMS)


def build_document_compare_prompt(document_a, chunks_a, document_b, chunks_b) -> str:
    chunk_blocks_a = "\n\n".join(
        f"[Document A / Chunk {row['chunk_index']}]\n{row['chunk_text']}"
        for row in chunks_a
    )
    chunk_blocks_b = "\n\n".join(
        f"[Document B / Chunk {row['chunk_index']}]\n{row['chunk_text']}"
        for row in chunks_b
    )
    return f"""
You are a legal document comparison analyst for Juris.

Compare two uploaded English legal documents. First identify each document type.
Then decide whether they appear comparable as the same general type or same legal/business purpose.
Examples of comparable pairs: two rental agreements, two NDAs, two employment agreements, two service agreements, two vendor contracts, two privacy policies, two versions of a purchase agreement, or two documents with substantially similar legal purpose.

Important rules:
- Use only the provided document chunks.
- Do not invent differences.
- Keep the comparison brief and easy to scan.
- Return at most 8 differences.
- Keep every difference concise: one short sentence per comparison field when possible.
- Focus on meaningful legal, financial, obligation, deadline, risk, and clause differences.
- If a difference is not supported by the chunks, do not include it.
- If the documents are not comparable, set "areComparable" to false, explain why in "summary", and keep "differences" empty unless there is a directly supported high-level mismatch.
- Include sourceReference using document and chunk numbers where possible, such as "A Chunk 2; B Chunk 4".
- Return only valid JSON. Do not include Markdown, explanations, or code fences.

Document A metadata:
- id: {document_a["id"]}
- name: {document_a["file_name"]}

Document B metadata:
- id: {document_b["id"]}
- name: {document_b["file_name"]}

Return this exact top-level JSON shape:
{{
  "documentA": {{
    "id": "",
    "name": "",
    "documentType": ""
  }},
  "documentB": {{
    "id": "",
    "name": "",
    "documentType": ""
  }},
  "areComparable": true,
  "summary": "",
  "differences": [
    {{
      "title": "",
      "type": "Changed",
      "category": "",
      "documentA": "",
      "documentB": "",
      "impact": "",
      "riskChange": "Not applicable",
      "affectedParty": "",
      "sourceReference": "",
      "confidence": 0
    }}
  ],
  "financialDifferences": [],
  "obligationDifferences": [],
  "deadlineDifferences": [],
  "riskDifferences": [],
  "recommendedQuestions": []
}}

Field guidance:
- "documentA.documentType" and "documentB.documentType": best supported type for each document.
- "areComparable": true only when the documents appear to be the same general document type or comparable legal/business purpose.
- "summary": under 120 words. Explain the main takeaway and whether the documents are comparable.
- "differences": the most important supported differences. Return no more than 8 items. Keep each item concise.
- "type": exactly one of "Added", "Removed", "Changed", or "Same".
- "category": legal category, such as Payment, Termination, Confidentiality, Liability, Renewal, Governing Law, Obligations, Rights, Deadlines, Risk, Privacy, IP, Employment, Data Use, or another document-appropriate category.
- "documentA": what Document A says or "Not specified" if the comparable term is absent from Document A.
- "documentB": what Document B says or "Not specified" if the comparable term is absent from Document B.
- "impact": why the difference matters in plain English.
- "riskChange": exactly one of "Lower", "Same", "Higher", or "Not applicable".
- "affectedParty": party or role most affected, or "Not specified" if unclear.
- "sourceReference": document/chunk references supporting the difference.
- "confidence": integer from 0 to 100 based on how clearly the difference is supported.
- "financialDifferences": concise supported money/payment/fee/deposit/penalty differences.
- "obligationDifferences": concise supported duty/responsibility differences.
- "deadlineDifferences": concise supported date/notice/renewal/expiry/timeline differences.
- "riskDifferences": concise supported risk or protection differences.
- "recommendedQuestions": exactly 5 short suggested follow-up questions for Chat.

Document A chunks:
{chunk_blocks_a}

Document B chunks:
{chunk_blocks_b}
""".strip()


async def save_document_metadata(
    pool: asyncpg.Pool,
    document_id: str,
    user_id: str,
    file_name: str,
    file_key: str,
    file_size: int,
    mime_type: str,
):
    return await pool.fetchrow(
        """
        insert into documents (
          id, user_id, title, file_name, file_key, file_size, mime_type,
          storage_provider, status, created_at
        )
        values ($1, $2, $3, $4, $5, $6, $7, 'cloudflare_r2', 'uploaded', now())
        on conflict (id) do update set
          file_name = excluded.file_name,
          file_key = excluded.file_key,
          file_size = excluded.file_size,
          mime_type = excluded.mime_type,
          status = 'uploaded'
        returning id, user_id, title, file_name, file_key, file_size, mime_type,
          storage_provider, status, created_at
        """,
        uuid.UUID(document_id),
        uuid.UUID(user_id),
        title_from_file(file_name),
        file_name,
        file_key,
        file_size,
        mime_type,
    )


async def save_document_text(
    pool: asyncpg.Pool,
    document_id: str,
    user_id: str,
    text_content: str,
    page_count: int,
):
    await pool.execute(
        """
        insert into document_text (
          document_id, user_id, text_content, page_count, language, created_at, updated_at
        )
        values ($1, $2, $3, $4, 'en', now(), now())
        on conflict (document_id) do update set
          text_content = excluded.text_content,
          page_count = excluded.page_count,
          language = 'en',
          updated_at = now()
        """,
        uuid.UUID(document_id),
        uuid.UUID(user_id),
        text_content,
        page_count,
    )


async def save_document_chunks(
    pool: asyncpg.Pool,
    document_id: str,
    user_id: str,
    chunks: list[str],
    embeddings: list[list[float]],
):
    if len(chunks) != len(embeddings):
        raise ValueError("Chunk and embedding counts must match.")

    document_uuid = uuid.UUID(document_id)
    user_uuid = uuid.UUID(user_id)
    async with pool.acquire() as connection:
        async with connection.transaction():
            await connection.execute("delete from document_chunks where document_id = $1", document_uuid)
            if chunks:
                await connection.executemany(
                    """
                    insert into document_chunks (
                      document_id, user_id, chunk_index, chunk_text, embedding,
                      embedding_provider, embedding_model, embedding_dimensions, created_at
                    )
                    values ($1, $2, $3, $4, $5::vector, $6, $7, $8, now())
                    """,
                    [
                        (
                            document_uuid,
                            user_uuid,
                            index,
                            chunk,
                            vector_literal(embeddings[index]),
                            "openai",
                            OPENAI_EMBED_MODEL,
                            EMBEDDING_DIMENSIONS,
                        )
                        for index, chunk in enumerate(chunks)
                    ],
                )


async def update_document_status(pool: asyncpg.Pool, document_id: str, user_id: str, status_value: str):
    return await pool.fetchrow(
        """
        update documents
        set status = $3
        where id = $1 and user_id = $2
        returning id, user_id, title, file_name, file_key, file_size, mime_type,
          storage_provider, status, created_at
        """,
        uuid.UUID(document_id),
        uuid.UUID(user_id),
        status_value,
    )


async def get_owned_document(pool: asyncpg.Pool, document_id: str, user_id: str):
    return await pool.fetchrow(
        """
        select id, user_id, title, file_name, status
        from documents
        where id = $1 and user_id = $2
        """,
        uuid.UUID(document_id),
        uuid.UUID(user_id),
    )


async def search_document_chunks(
    pool: asyncpg.Pool,
    document_id: str,
    question_embedding: list[float],
    limit: int = 3,
):
    return await pool.fetch(
        """
        select
          id,
          chunk_index,
          chunk_text,
          embedding::vector(1536) <=> $2::vector(1536) as distance
        from document_chunks
        where document_id = $1
          and embedding is not null
          and embedding_provider = 'openai'
          and embedding_model = 'text-embedding-3-small'
          and embedding_dimensions = 1536
        order by distance asc
        limit $3
        """,
        uuid.UUID(document_id),
        vector_literal(question_embedding),
        limit,
    )


async def get_fallback_document_chunks(pool: asyncpg.Pool, document_id: str, limit: int = 3):
    return await pool.fetch(
        """
        select
          id,
          chunk_index,
          chunk_text,
          null::float8 as distance
        from document_chunks
        where document_id = $1
          and embedding is not null
          and embedding_provider = 'openai'
          and embedding_model = 'text-embedding-3-small'
          and embedding_dimensions = 1536
        order by chunk_index asc
        limit $2
        """,
        uuid.UUID(document_id),
        limit,
    )


async def count_retrievable_document_chunks(pool: asyncpg.Pool, document_id: str) -> int:
    return await pool.fetchval(
        """
        select count(*)
        from document_chunks
        where document_id = $1
          and embedding is not null
          and embedding_provider = 'openai'
          and embedding_model = 'text-embedding-3-small'
          and embedding_dimensions = 1536
        """,
        uuid.UUID(document_id),
    )


async def get_document_chunks_in_order(pool: asyncpg.Pool, document_id: str, user_id: str):
    return await pool.fetch(
        """
        select chunk_index, chunk_text
        from document_chunks
        where document_id = $1
          and user_id = $2
        order by chunk_index asc
        """,
        uuid.UUID(document_id),
        uuid.UUID(user_id),
    )


async def get_document_page_count(pool: asyncpg.Pool, document_id: str, user_id: str) -> int | None:
    row = await pool.fetchrow(
        """
        select page_count
        from document_text
        where document_id = $1
          and user_id = $2
        """,
        uuid.UUID(document_id),
        uuid.UUID(user_id),
    )
    return row["page_count"] if row else None


async def get_document_version_stamp(pool: asyncpg.Pool, document_id: str, user_id: str):
    row = await pool.fetchrow(
        """
        select
          d.id,
          d.file_key,
          d.file_size,
          d.mime_type,
          d.status,
          d.created_at,
          coalesce(dt.updated_at, d.created_at) as updated_at
        from documents d
        left join document_text dt
          on dt.document_id = d.id and dt.user_id = d.user_id
        where d.id = $1
          and d.user_id = $2
        """,
        uuid.UUID(document_id),
        uuid.UUID(user_id),
    )
    if not row:
        return {}
    return {
        "id": str(row["id"]),
        "fileKey": row["file_key"],
        "fileSize": row["file_size"],
        "mimeType": row["mime_type"],
        "status": row["status"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


async def document_feature_input_hash(
    pool: asyncpg.Pool,
    *,
    document_id: str,
    user_id: str,
    feature: str,
    chunks,
) -> str:
    version = await get_document_version_stamp(pool, document_id, user_id)
    return build_input_hash(
        {
            "feature": feature,
            "document": version,
            "chunkHash": chunk_content_hash(chunks),
        }
    )


async def compare_feature_input_hash(
    pool: asyncpg.Pool,
    *,
    document_a_id: str,
    document_b_id: str,
    user_id: str,
    chunks_a,
    chunks_b,
) -> str:
    version_a = await get_document_version_stamp(pool, document_a_id, user_id)
    version_b = await get_document_version_stamp(pool, document_b_id, user_id)
    return build_input_hash(
        {
            "feature": "compare_documents",
            "documentA": {
                "id": document_a_id,
                "updatedAt": version_a.get("updatedAt"),
                "chunkHash": chunk_content_hash(chunks_a),
            },
            "documentB": {
                "id": document_b_id,
                "updatedAt": version_b.get("updatedAt"),
                "chunkHash": chunk_content_hash(chunks_b),
            },
        }
    )


async def get_cached_ai_output(
    pool: asyncpg.Pool,
    *,
    document_id: str,
    user_id: str,
    feature: str,
    input_hash: str,
) -> dict | None:
    row = await pool.fetchrow(
        """
        select output_json
        from ai_outputs
        where document_id = $1
          and user_id = $2
          and feature = $3
          and input_hash = $4
        """,
        uuid.UUID(document_id),
        uuid.UUID(user_id),
        feature,
        input_hash,
    )
    if not row:
        return None
    return decode_ai_output(row["output_json"])


async def save_ai_output(
    pool: asyncpg.Pool,
    *,
    document_id: str,
    user_id: str,
    feature: str,
    input_hash: str,
    output_json: dict,
):
    await pool.execute(
        """
        insert into ai_outputs (
          document_id, user_id, feature, input_hash, output_json, created_at, updated_at
        )
        values ($1, $2, $3, $4, $5::jsonb, now(), now())
        on conflict (document_id, feature, input_hash) do update set
          output_json = excluded.output_json,
          updated_at = now()
        """,
        uuid.UUID(document_id),
        uuid.UUID(user_id),
        feature,
        input_hash,
        stable_json(output_json),
    )


def with_cached_flag(output: dict, cached: bool) -> dict:
    normalized = dict(output)
    normalized["cached"] = cached
    return normalized


@app.get("/api/juris-compass/conversations")
async def list_compass_conversations(
    user_id: Annotated[str, Depends(current_user_id)],
    pool: Annotated[asyncpg.Pool, Depends(get_db_pool)],
):
    req_id = request_id()
    rows = await pool.fetch(
        """
        select
          c.id,
          c.title,
          c.jurisdiction,
          c.created_at,
          c.updated_at,
          (
            select count(*)
            from juris_compass_messages m
            where m.conversation_id = c.id
          ) as message_count,
          (
            select m.content
            from juris_compass_messages m
            where m.conversation_id = c.id
            order by m.created_at desc
            limit 1
          ) as preview
        from juris_compass_conversations c
        where c.user_id = $1
        order by c.updated_at desc
        limit 50
        """,
        uuid.UUID(user_id),
    )
    return success_envelope([compass_conversation_payload(row) for row in rows], req_id)


@app.get("/api/juris-compass/conversations/{conversation_id}")
async def get_compass_conversation(
    conversation_id: str,
    user_id: Annotated[str, Depends(current_user_id)],
    pool: Annotated[asyncpg.Pool, Depends(get_db_pool)],
):
    req_id = request_id()
    normalized_id = normalize_compass_conversation_id(conversation_id)
    conversation = await pool.fetchrow(
        """
        select id, title, jurisdiction, created_at, updated_at,
          (select count(*) from juris_compass_messages where conversation_id = $1) as message_count,
          null::text as preview
        from juris_compass_conversations
        where id = $1 and user_id = $2
        """,
        uuid.UUID(normalized_id),
        uuid.UUID(user_id),
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Compass conversation not found.")

    messages = await pool.fetch(
        """
        select id, role, content, response_json, created_at
        from juris_compass_messages
        where conversation_id = $1 and user_id = $2
        order by created_at asc
        """,
        uuid.UUID(normalized_id),
        uuid.UUID(user_id),
    )
    data = compass_conversation_payload(conversation)
    data["messages"] = [compass_message_payload(row) for row in messages]
    return success_envelope(data, req_id)


@app.patch("/api/juris-compass/conversations/{conversation_id}")
async def update_compass_conversation(
    conversation_id: str,
    payload: CompassConversationUpdateRequest,
    user_id: Annotated[str, Depends(current_user_id)],
    pool: Annotated[asyncpg.Pool, Depends(get_db_pool)],
):
    req_id = request_id()
    normalized_id = normalize_compass_conversation_id(conversation_id)
    title = str(payload.title or "").strip()
    jurisdiction = normalize_compass_jurisdiction(payload.jurisdiction) if payload.jurisdiction else None
    if payload.title is not None and not 2 <= len(title) <= 80:
        raise HTTPException(status_code=400, detail="Conversation title must be between 2 and 80 characters.")
    if payload.title is None and jurisdiction is None:
        raise HTTPException(status_code=400, detail="Provide a title or jurisdiction to update.")

    row = await pool.fetchrow(
        """
        update juris_compass_conversations
        set title = coalesce($3, title),
            jurisdiction = coalesce($4, jurisdiction),
            updated_at = now()
        where id = $1 and user_id = $2
        returning id, title, jurisdiction, created_at, updated_at,
          (select count(*) from juris_compass_messages where conversation_id = $1) as message_count,
          null::text as preview
        """,
        uuid.UUID(normalized_id),
        uuid.UUID(user_id),
        title if payload.title is not None else None,
        jurisdiction,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Compass conversation not found.")
    return success_envelope(compass_conversation_payload(row), req_id)


@app.delete("/api/juris-compass/conversations/{conversation_id}")
async def delete_compass_conversation(
    conversation_id: str,
    user_id: Annotated[str, Depends(current_user_id)],
    pool: Annotated[asyncpg.Pool, Depends(get_db_pool)],
):
    req_id = request_id()
    normalized_id = normalize_compass_conversation_id(conversation_id)
    result = await pool.execute(
        """
        delete from juris_compass_conversations
        where id = $1 and user_id = $2
        """,
        uuid.UUID(normalized_id),
        uuid.UUID(user_id),
    )
    if result != "DELETE 1":
        raise HTTPException(status_code=404, detail="Compass conversation not found.")
    return success_envelope({"ok": True}, req_id)


@app.post("/api/juris-compass/chat")
async def juris_compass_chat(
    payload: CompassChatRequest,
    request: Request,
    user_id: Annotated[str, Depends(current_user_id)],
    pool: Annotated[asyncpg.Pool, Depends(get_db_pool)],
):
    req_id = request.headers.get("x-request-id") or request_id()
    message = re.sub(r"\s+", " ", str(payload.message or "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="Compass question is required.")
    if len(message) > COMPASS_MAX_MESSAGE_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Compass questions must be {COMPASS_MAX_MESSAGE_CHARS} characters or fewer.",
        )

    jurisdiction = normalize_compass_jurisdiction(payload.jurisdiction)
    normalized_id = normalize_compass_conversation_id(payload.conversation_id)
    conversation = None
    history = []

    if normalized_id:
        conversation = await pool.fetchrow(
            """
            select id, title, jurisdiction, created_at, updated_at
            from juris_compass_conversations
            where id = $1 and user_id = $2
            """,
            uuid.UUID(normalized_id),
            uuid.UUID(user_id),
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Compass conversation not found.")
        history_rows = await pool.fetch(
            """
            select role, content
            from (
              select role, content, created_at
              from juris_compass_messages
              where conversation_id = $1 and user_id = $2
              order by created_at desc
              limit $3
            ) recent
            order by created_at asc
            """,
            uuid.UUID(normalized_id),
            uuid.UUID(user_id),
            COMPASS_HISTORY_LIMIT,
        )
        history = [dict(row) for row in history_rows]
    else:
        normalized_id = str(uuid.uuid4())

    checked_at = datetime.now(timezone.utc).date().isoformat()
    try:
        research = await generate_compass_research(
            jurisdiction=jurisdiction,
            message=message,
            history=history,
            checked_at=checked_at,
        )
    except AIProviderError as exc:
        log_exception(
            "juris_compass",
            exc,
            req_id,
            jurisdiction=jurisdiction,
            model=exc.model or OPENAI_COMPASS_MODEL,
        )
        return error_envelope_response(
            message=str(exc),
            request_id_value=req_id,
            status_code_value=exc.status_code,
            error_type=exc.error_type,
            details={
                "model": exc.model or OPENAI_COMPASS_MODEL,
                "rawResponse": sanitize_log_text(exc.raw_response, limit=2000),
            },
        )

    conversation_title = conversation["title"] if conversation else compass_conversation_title(message)
    research["conversationId"] = normalized_id
    research["conversationTitle"] = conversation_title

    async with pool.acquire() as connection:
        async with connection.transaction():
            if not conversation:
                await connection.execute(
                    """
                    insert into juris_compass_conversations (
                      id, user_id, title, jurisdiction, created_at, updated_at
                    ) values ($1, $2, $3, $4, now(), now())
                    """,
                    uuid.UUID(normalized_id),
                    uuid.UUID(user_id),
                    conversation_title,
                    jurisdiction,
                )
            else:
                await connection.execute(
                    """
                    update juris_compass_conversations
                    set jurisdiction = $3, updated_at = now()
                    where id = $1 and user_id = $2
                    """,
                    uuid.UUID(normalized_id),
                    uuid.UUID(user_id),
                    jurisdiction,
                )

            await connection.executemany(
                """
                insert into juris_compass_messages (
                  id, conversation_id, user_id, role, content, response_json, created_at
                ) values ($1, $2, $3, $4, $5, $6::jsonb, now())
                """,
                [
                    (
                        uuid.uuid4(),
                        uuid.UUID(normalized_id),
                        uuid.UUID(user_id),
                        "user",
                        message,
                        None,
                    ),
                    (
                        uuid.uuid4(),
                        uuid.UUID(normalized_id),
                        uuid.UUID(user_id),
                        "assistant",
                        research["answer"],
                        stable_json(research),
                    ),
                ],
            )

    return success_envelope(research, req_id)


@app.post("/api/documents/upload", response_model=DocumentRecord)
async def upload_document(
    file: Annotated[UploadFile, File()],
    user_id: Annotated[str, Depends(current_user_id)],
    pool: Annotated[asyncpg.Pool, Depends(get_db_pool)],
):
    try:
        print("auth verified")
        file_name = file.filename or "document"
        contents = await file.read(MAX_FILE_SIZE + 1)
        file_size = len(contents)
        mime_type = validate_uploaded_file(file_name, file.content_type, file_size, contents)
        print("file validated")

        document_id = str(uuid.uuid4())
        file_key = user_file_key(user_id, document_id, file_name)

        print("r2 upload starting")
        get_r2_client().put_object(
            Bucket=get_env("R2_BUCKET_NAME"),
            Key=file_key,
            Body=contents,
            ContentType=mime_type,
        )
        print("r2 upload done")

        print("database insert starting")
        row = await save_document_metadata(
            pool=pool,
            document_id=document_id,
            user_id=user_id,
            file_name=file_name,
            file_key=file_key,
            file_size=file_size,
            mime_type=mime_type,
        )
        print("database insert done")
        if mime_type == "application/pdf":
            try:
                print("pdf extraction starting")
                extracted_text, page_count = extract_pdf_text(contents)
                await save_document_text(
                    pool=pool,
                    document_id=document_id,
                    user_id=user_id,
                    text_content=extracted_text,
                    page_count=page_count,
                )
                chunks = chunk_text(extracted_text)
                print("chunk embedding starting")
                embeddings = await generate_embeddings(chunks)
                await save_document_chunks(pool, document_id, user_id, chunks, embeddings)
                print("chunk embedding done")
                row = await update_document_status(pool, document_id, user_id, "processed")
                print("pdf extraction done")
            except Exception as exc:
                traceback.print_exc()
                row = await update_document_status(pool, document_id, user_id, "extraction_failed")
                print(f"pdf extraction failed: {exc}")

        return document_record(row)
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Upload failed",
                "error": str(exc),
                "type": exc.__class__.__name__,
            },
        )


@app.get("/api/documents", response_model=list[DocumentRecord])
async def list_documents(
    user_id: Annotated[str, Depends(current_user_id)],
    pool: Annotated[asyncpg.Pool, Depends(get_db_pool)],
):
    rows = await pool.fetch(
        """
        select id, user_id, title, file_name, file_key, file_size, mime_type,
          storage_provider, status, created_at
        from documents
        where user_id = $1
        order by created_at desc
        """,
        uuid.UUID(user_id),
    )
    return [document_record(row) for row in rows]


@app.get("/api/documents/{document_id}/download-url", response_model=DownloadUrlResponse)
async def download_url(
    document_id: str,
    user_id: Annotated[str, Depends(current_user_id)],
    pool: Annotated[asyncpg.Pool, Depends(get_db_pool)],
):
    row = await pool.fetchrow(
        "select file_key from documents where id = $1 and user_id = $2",
        uuid.UUID(document_id),
        uuid.UUID(user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        signed_url = get_r2_client().generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": get_env("R2_BUCKET_NAME"), "Key": row["file_key"]},
            ExpiresIn=300,
            HttpMethod="GET",
        )
    except ClientError as exc:
        raise HTTPException(status_code=500, detail="Could not create download URL.") from exc

    return DownloadUrlResponse(downloadUrl=signed_url)


@app.post("/api/documents/{document_id}/ask", response_model=AskDocumentResponse)
async def ask_document(
    document_id: str,
    request: AskDocumentRequest,
    user_id: Annotated[str, Depends(current_user_id)],
    pool: Annotated[asyncpg.Pool, Depends(get_db_pool)],
):
    print(f"[rag:ask:start] document_id={document_id} user_id={user_id}")
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    document = await get_owned_document(pool, document_id, user_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    question_embedding = (await generate_embeddings([question], task_type="RETRIEVAL_QUERY"))[0]
    print(
        f"[rag:ask:embedding] document_id={document_id} "
        f"question_embedding_dimensions={len(question_embedding)}"
    )
    retrievable_chunk_count = await count_retrievable_document_chunks(pool, document_id)
    print(
        f"[rag:ask:chunks_before_vector_search] document_id={document_id} "
        f"chunk_count={retrievable_chunk_count}"
    )
    chunks = await search_document_chunks(
        pool=pool,
        document_id=document_id,
        question_embedding=question_embedding,
        limit=3,
    )
    print(
        f"[rag:ask:chunks_after_vector_search] document_id={document_id} "
        f"chunk_count={len(chunks)}"
    )
    print(
        f"[rag:ask:vector_results] document_id={document_id} "
        f"results={[{'chunk_index': row['chunk_index'], 'distance': row['distance']} for row in chunks]}"
    )

    if retrievable_chunk_count > 0 and not chunks:
        print(
            f"[rag:ask:fallback] document_id={document_id} "
            "vector_search_returned_zero=true fallback=chunk_index"
        )
        chunks = await get_fallback_document_chunks(pool, document_id, limit=3)
        print(
            f"[rag:ask:fallback_results] document_id={document_id} "
            f"results={[{'chunk_index': row['chunk_index'], 'distance': row['distance']} for row in chunks]}"
        )

    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="No matching document chunks found for this document.",
        )

    prompt = build_document_answer_prompt(question, chunks)
    answer = await generate_answer(prompt)
    if not answer:
        answer = "I could not find that information in this document."

    return AskDocumentResponse(
        answer=answer,
        sources=[
            AskSource(chunk_index=row["chunk_index"], preview=chunk_preview(row["chunk_text"]))
            for row in chunks
        ],
    )


@app.post("/api/documents/{document_id}/summary")
async def summarize_document(
    request: Request,
    document_id: str,
    user_id: Annotated[str, Depends(current_user_id)],
    pool: Annotated[asyncpg.Pool, Depends(get_db_pool)],
):
    req_id = request.headers.get("x-request-id") or request_id()
    print(
        f"[ai:summary:start] request_id={req_id} document_id={document_id} "
        f"user_id={user_id} ai_provider=openai model={OPENAI_ANALYSIS_MODEL} "
        f"timeout_seconds={AI_TIMEOUT_SECONDS}"
    )
    try:
        document = await get_owned_document(pool, document_id, user_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found.")

        chunks = await get_document_chunks_in_order(pool, document_id, user_id)
        print(f"[ai:summary:chunks] request_id={req_id} chunk_count={len(chunks)}")
        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="Document has no processed text chunks available for summary.",
            )

        feature = "executive_summary"
        input_hash = await document_feature_input_hash(
            pool,
            document_id=document_id,
            user_id=user_id,
            feature=feature,
            chunks=chunks,
        )
        cached_output = await get_cached_ai_output(
            pool,
            document_id=document_id,
            user_id=user_id,
            feature=feature,
            input_hash=input_hash,
        )
        if cached_output is not None:
            print(f"[ai:summary:cache_hit] request_id={req_id} input_hash={input_hash}")
            return success_envelope(with_cached_flag(cached_output, True), req_id)

        prompt = build_document_summary_prompt(chunks)
        summary = await generate_summary(prompt)
        if not summary:
            raise AIProviderError(
                "AI provider returned an empty executive summary.",
                error_type="EmptyAIResponse",
                status_code=502,
            )

        output = {"summary": summary}
        await save_ai_output(
            pool,
            document_id=document_id,
            user_id=user_id,
            feature=feature,
            input_hash=input_hash,
            output_json=output,
        )
        print(f"[ai:summary:success] request_id={req_id} response_chars={len(summary)}")
        return success_envelope(with_cached_flag(output, False), req_id)
    except HTTPException as exc:
        return error_envelope_response(
            message=str(exc.detail),
            request_id_value=req_id,
            status_code_value=exc.status_code,
            error_type="HTTPException",
        )
    except AIProviderError as exc:
        log_exception("ai_summary", exc, req_id, provider="openai", model=exc.model, raw_response=sanitize_log_text(exc.raw_response))
        return error_envelope_response(
            message=str(exc),
            request_id_value=req_id,
            status_code_value=exc.status_code,
            error_type=exc.error_type,
            details={
                "provider": "openai",
                "model": exc.model,
                "timeoutSeconds": AI_TIMEOUT_SECONDS,
                "rawResponse": sanitize_log_text(exc.raw_response),
            },
        )
    except Exception as exc:
        log_exception("summary_endpoint", exc, req_id)
        return error_envelope_response(
            message=str(exc),
            request_id_value=req_id,
            status_code_value=500,
            error_type=exc.__class__.__name__,
        )


@app.post("/api/documents/{document_id}/intelligence")
async def document_intelligence(
    request: Request,
    document_id: str,
    user_id: Annotated[str, Depends(current_user_id)],
    pool: Annotated[asyncpg.Pool, Depends(get_db_pool)],
):
    req_id = request.headers.get("x-request-id") or request_id()
    print(
        f"[ai:intelligence:start] request_id={req_id} document_id={document_id} "
        f"user_id={user_id} ai_provider=openai model={OPENAI_ANALYSIS_MODEL} "
        f"timeout_seconds={AI_TIMEOUT_SECONDS}"
    )
    try:
        document = await get_owned_document(pool, document_id, user_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found.")

        chunks = await get_document_chunks_in_order(pool, document_id, user_id)
        print(f"[ai:intelligence:chunks] request_id={req_id} chunk_count={len(chunks)}")
        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="Document has no processed text chunks available for intelligence.",
            )

        feature = "document_intelligence"
        input_hash = await document_feature_input_hash(
            pool,
            document_id=document_id,
            user_id=user_id,
            feature=feature,
            chunks=chunks,
        )
        cached_output = await get_cached_ai_output(
            pool,
            document_id=document_id,
            user_id=user_id,
            feature=feature,
            input_hash=input_hash,
        )
        if cached_output is not None:
            print(f"[ai:intelligence:cache_hit] request_id={req_id} input_hash={input_hash}")
            return success_envelope(with_cached_flag(cached_output, True), req_id)

        page_count = await get_document_page_count(pool, document_id, user_id)
        prompt = build_document_intelligence_prompt(chunks, page_count)
        intelligence = await generate_intelligence(prompt)
        normalized = normalize_intelligence_payload(intelligence)
        await save_ai_output(
            pool,
            document_id=document_id,
            user_id=user_id,
            feature=feature,
            input_hash=input_hash,
            output_json=normalized,
        )
        print(f"[ai:intelligence:success] request_id={req_id} keys={list(normalized.keys())}")
        return success_envelope(with_cached_flag(normalized, False), req_id)
    except HTTPException as exc:
        return error_envelope_response(
            message=str(exc.detail),
            request_id_value=req_id,
            status_code_value=exc.status_code,
            error_type="HTTPException",
        )
    except AIProviderError as exc:
        log_exception("ai_intelligence", exc, req_id, provider="openai", model=exc.model, raw_response=sanitize_log_text(exc.raw_response))
        return error_envelope_response(
            message=str(exc),
            request_id_value=req_id,
            status_code_value=exc.status_code,
            error_type=exc.error_type,
            details=ai_error_details,
        )
    except Exception as exc:
        log_exception("intelligence_endpoint", exc, req_id)
        return error_envelope_response(
            message=str(exc),
            request_id_value=req_id,
            status_code_value=500,
            error_type=exc.__class__.__name__,
        )


@app.post("/api/documents/{document_id}/clauses")
async def document_clauses(
    request: Request,
    document_id: str,
    user_id: Annotated[str, Depends(current_user_id)],
    pool: Annotated[asyncpg.Pool, Depends(get_db_pool)],
):
    req_id = request.headers.get("x-request-id") or request_id()
    print(
        f"[ai:clauses:start] request_id={req_id} document_id={document_id} "
        f"user_id={user_id} ai_provider=openai model={OPENAI_ANALYSIS_MODEL} "
        f"timeout_seconds={AI_TIMEOUT_SECONDS}"
    )
    try:
        document = await get_owned_document(pool, document_id, user_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found.")

        chunks = await get_document_chunks_in_order(pool, document_id, user_id)
        print(f"[ai:clauses:chunks] request_id={req_id} chunk_count={len(chunks)}")
        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="Document has no processed text chunks available for clause intelligence.",
            )

        feature = "clause_intelligence"
        input_hash = await document_feature_input_hash(
            pool,
            document_id=document_id,
            user_id=user_id,
            feature=feature,
            chunks=chunks,
        )
        cached_output = await get_cached_ai_output(
            pool,
            document_id=document_id,
            user_id=user_id,
            feature=feature,
            input_hash=input_hash,
        )
        if cached_output is not None:
            print(f"[ai:clauses:cache_hit] request_id={req_id} input_hash={input_hash}")
            return success_envelope(with_cached_flag(cached_output, True), req_id)

        prompt = build_document_clauses_prompt(chunks)
        clauses = await generate_clauses(prompt)
        normalized = normalize_clauses_payload(clauses)
        await save_ai_output(
            pool,
            document_id=document_id,
            user_id=user_id,
            feature=feature,
            input_hash=input_hash,
            output_json=normalized,
        )
        print(
            f"[ai:clauses:success] request_id={req_id} "
            f"document_type={normalized.get('documentType')} "
            f"clause_count={len(normalized.get('clauses', []))}"
        )
        return success_envelope(with_cached_flag(normalized, False), req_id)
    except HTTPException as exc:
        return error_envelope_response(
            message=str(exc.detail),
            request_id_value=req_id,
            status_code_value=exc.status_code,
            error_type="HTTPException",
        )
    except AIProviderError as exc:
        log_exception("ai_clauses", exc, req_id, provider="openai", model=exc.model, raw_response=sanitize_log_text(exc.raw_response))
        return error_envelope_response(
            message=str(exc),
            request_id_value=req_id,
            status_code_value=exc.status_code,
            error_type=exc.error_type,
            details={
                "provider": "openai",
                "model": exc.model,
                "timeoutSeconds": AI_TIMEOUT_SECONDS,
                "rawResponse": sanitize_log_text(exc.raw_response),
            },
        )
    except Exception as exc:
        log_exception("clauses_endpoint", exc, req_id)
        return error_envelope_response(
            message=str(exc),
            request_id_value=req_id,
            status_code_value=500,
            error_type=exc.__class__.__name__,
        )


@app.post("/api/documents/{document_id}/risk-analysis")
async def document_risk_analysis(
    request: Request,
    document_id: str,
    user_id: Annotated[str, Depends(current_user_id)],
    pool: Annotated[asyncpg.Pool, Depends(get_db_pool)],
):
    req_id = request.headers.get("x-request-id") or request_id()
    print(
        f"[ai:risk:start] request_id={req_id} document_id={document_id} "
        f"user_id={user_id} ai_provider=openai model={OPENAI_ANALYSIS_MODEL} "
        f"timeout_seconds={AI_TIMEOUT_SECONDS}"
    )
    try:
        document = await get_owned_document(pool, document_id, user_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found.")

        chunks = await get_document_chunks_in_order(pool, document_id, user_id)
        print(f"[ai:risk:chunks] request_id={req_id} chunk_count={len(chunks)}")
        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="Document has no processed text chunks available for risk analysis.",
            )

        feature = "risk_analysis"
        input_hash = await document_feature_input_hash(
            pool,
            document_id=document_id,
            user_id=user_id,
            feature=feature,
            chunks=chunks,
        )
        cached_output = await get_cached_ai_output(
            pool,
            document_id=document_id,
            user_id=user_id,
            feature=feature,
            input_hash=input_hash,
        )
        if cached_output is not None:
            print(f"[ai:risk:cache_hit] request_id={req_id} input_hash={input_hash}")
            return success_envelope(with_cached_flag(cached_output, True), req_id)

        prompt = build_document_risk_analysis_prompt(chunks)
        risk_analysis = await generate_risk_analysis(prompt)
        normalized = normalize_risk_analysis_payload(risk_analysis)
        await save_ai_output(
            pool,
            document_id=document_id,
            user_id=user_id,
            feature=feature,
            input_hash=input_hash,
            output_json=normalized,
        )
        print(
            f"[ai:risk:success] request_id={req_id} "
            f"document_type={normalized.get('documentType')} "
            f"overall_risk={normalized.get('overallRisk')} "
            f"risk_count={len(normalized.get('risks', []))}"
        )
        return success_envelope(with_cached_flag(normalized, False), req_id)
    except HTTPException as exc:
        return error_envelope_response(
            message=str(exc.detail),
            request_id_value=req_id,
            status_code_value=exc.status_code,
            error_type="HTTPException",
        )
    except AIProviderError as exc:
        log_exception("ai_risk_analysis", exc, req_id, provider="openai", model=exc.model, raw_response=sanitize_log_text(exc.raw_response))
        return error_envelope_response(
            message=str(exc),
            request_id_value=req_id,
            status_code_value=exc.status_code,
            error_type=exc.error_type,
            details={
                "provider": "openai",
                "model": exc.model,
                "timeoutSeconds": AI_TIMEOUT_SECONDS,
                "rawResponse": sanitize_log_text(exc.raw_response),
            },
        )
    except Exception as exc:
        log_exception("risk_analysis_endpoint", exc, req_id)
        return error_envelope_response(
            message=str(exc),
            request_id_value=req_id,
            status_code_value=500,
            error_type=exc.__class__.__name__,
        )


@app.post("/api/documents/{document_id}/compare")
async def compare_documents(
    request: Request,
    document_id: str,
    payload: CompareDocumentsRequest,
    user_id: Annotated[str, Depends(current_user_id)],
    pool: Annotated[asyncpg.Pool, Depends(get_db_pool)],
):
    req_id = request.headers.get("x-request-id") or request_id()
    print(
        f"[ai:compare:start] request_id={req_id} document_id={document_id} "
        f"second_document_id={payload.second_document_id} user_id={user_id} "
        f"ai_provider=openai model={OPENAI_ANALYSIS_MODEL} timeout_seconds={COMPARE_TIMEOUT_SECONDS} "
        f"max_output_tokens={COMPARE_MAX_OUTPUT_TOKENS}"
    )
    try:
        try:
            current_document_id = str(uuid.UUID(document_id))
            second_document_id = str(uuid.UUID(payload.second_document_id))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Valid document IDs are required.") from exc

        if current_document_id == second_document_id:
            raise HTTPException(status_code=400, detail="Choose a different document to compare.")

        document_a = await get_owned_document(pool, current_document_id, user_id)
        if not document_a:
            raise HTTPException(status_code=404, detail="Document not found.")

        document_b = await get_owned_document(pool, second_document_id, user_id)
        if not document_b:
            raise HTTPException(status_code=404, detail="Second document not found.")

        chunks_a = await get_document_chunks_in_order(pool, current_document_id, user_id)
        chunks_b = await get_document_chunks_in_order(pool, second_document_id, user_id)
        print(
            f"[ai:compare:chunks] request_id={req_id} "
            f"document_a_chunks={len(chunks_a)} document_b_chunks={len(chunks_b)}"
        )
        if not chunks_a:
            raise HTTPException(
                status_code=400,
                detail="Current document has no processed text chunks available for comparison.",
            )
        if not chunks_b:
            raise HTTPException(
                status_code=400,
                detail="Second document has no processed text chunks available for comparison.",
            )

        feature = "compare_documents"
        input_hash = await compare_feature_input_hash(
            pool,
            document_a_id=current_document_id,
            document_b_id=second_document_id,
            user_id=user_id,
            chunks_a=chunks_a,
            chunks_b=chunks_b,
        )
        cached_output = await get_cached_ai_output(
            pool,
            document_id=current_document_id,
            user_id=user_id,
            feature=feature,
            input_hash=input_hash,
        )
        if cached_output is not None:
            print(f"[ai:compare:cache_hit] request_id={req_id} input_hash={input_hash}")
            return success_envelope(with_cached_flag(cached_output, True), req_id)

        compare_chunks_a = select_compare_chunks(chunks_a)
        compare_chunks_b = select_compare_chunks(chunks_b)
        compare_chars_a = sum(len(row["chunk_text"] or "") for row in compare_chunks_a)
        compare_chars_b = sum(len(row["chunk_text"] or "") for row in compare_chunks_b)
        print(
            f"[ai:compare:selected_chunks] request_id={req_id} "
            f"document_a_selected={len(compare_chunks_a)} document_a_chars={compare_chars_a} "
            f"document_b_selected={len(compare_chunks_b)} document_b_chars={compare_chars_b} "
            f"char_budget_per_document={COMPARE_CONTEXT_CHAR_BUDGET}"
        )

        prompt = build_document_compare_prompt(document_a, compare_chunks_a, document_b, compare_chunks_b)
        comparison = await generate_document_compare(prompt)
        normalized = normalize_compare_payload(comparison, document_a, document_b)
        await save_ai_output(
            pool,
            document_id=current_document_id,
            user_id=user_id,
            feature=feature,
            input_hash=input_hash,
            output_json=normalized,
        )
        print(
            f"[ai:compare:success] request_id={req_id} "
            f"are_comparable={normalized.get('areComparable')} "
            f"difference_count={len(normalized.get('differences', []))}"
        )
        return success_envelope(with_cached_flag(normalized, False), req_id)
    except HTTPException as exc:
        return error_envelope_response(
            message=str(exc.detail),
            request_id_value=req_id,
            status_code_value=exc.status_code,
            error_type="HTTPException",
        )
    except AIProviderError as exc:
        log_exception("ai_compare_documents", exc, req_id, provider="openai", model=exc.model, raw_response=sanitize_log_text(exc.raw_response))
        ai_error_details = None if exc.error_type in {"EmptyOpenAIResponse", "APITimeoutError", "TimeoutError"} else {
            "provider": "openai",
            "model": exc.model,
            "timeoutSeconds": COMPARE_TIMEOUT_SECONDS,
            "rawResponse": sanitize_log_text(exc.raw_response),
        }
        return error_envelope_response(
            message=str(exc),
            request_id_value=req_id,
            status_code_value=exc.status_code,
            error_type=exc.error_type,
            details={
                "provider": "openai",
                "model": exc.model,
                "timeoutSeconds": AI_TIMEOUT_SECONDS,
                "rawResponse": sanitize_log_text(exc.raw_response),
            },
        )
    except Exception as exc:
        log_exception("compare_endpoint", exc, req_id)
        return error_envelope_response(
            message=str(exc),
            request_id_value=req_id,
            status_code_value=500,
            error_type=exc.__class__.__name__,
        )


@app.delete("/api/documents/{document_id}")
async def delete_document(
    document_id: str,
    user_id: Annotated[str, Depends(current_user_id)],
    pool: Annotated[asyncpg.Pool, Depends(get_db_pool)],
):
    row = await pool.fetchrow(
        "select file_key from documents where id = $1 and user_id = $2",
        uuid.UUID(document_id),
        uuid.UUID(user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        get_r2_client().delete_object(Bucket=get_env("R2_BUCKET_NAME"), Key=row["file_key"])
    except ClientError as exc:
        raise HTTPException(status_code=500, detail="Could not delete file from storage.") from exc

    await pool.execute(
        "delete from documents where id = $1 and user_id = $2",
        uuid.UUID(document_id),
        uuid.UUID(user_id),
    )
    return {"ok": True}


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/debug/openai")
async def debug_openai():
    result = {
        "openai_key_detected": bool(os.getenv("OPENAI_API_KEY")),
        "embed_model": OPENAI_EMBED_MODEL,
        "chat_model": OPENAI_CHAT_MODEL,
        "httpx_status": None,
        "httpx_error_type": None,
        "httpx_error_message": None,
        "openai_sdk_models_ok": False,
        "openai_sdk_models_error_type": None,
        "openai_sdk_models_error_message": None,
        "tiny_embedding_ok": False,
        "tiny_embedding_error_type": None,
        "tiny_embedding_error_message": None,
        "tiny_embedding_dimensions": None,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
            )
        result["httpx_status"] = response.status_code
        if response.status_code >= 400:
            result["httpx_error_type"] = "HTTPStatusError"
            result["httpx_error_message"] = sanitize_log_text(response.text, limit=2000)
    except Exception as exc:
        result["httpx_error_type"] = exc.__class__.__name__
        result["httpx_error_message"] = str(exc)

    try:
        await asyncio.to_thread(lambda: get_openai_client().models.list())
        result["openai_sdk_models_ok"] = True
    except Exception as exc:
        result["openai_sdk_models_error_type"] = exc.__class__.__name__
        result["openai_sdk_models_error_message"] = openai_error_detail(exc)

    try:
        response = await asyncio.to_thread(
            lambda: get_openai_client().embeddings.create(
                model=OPENAI_EMBED_MODEL,
                input="hello",
            )
        )
        embedding = response.data[0].embedding if response.data else []
        result["tiny_embedding_ok"] = True
        result["tiny_embedding_dimensions"] = len(embedding)
    except Exception as exc:
        result["tiny_embedding_error_type"] = exc.__class__.__name__
        result["tiny_embedding_error_message"] = openai_error_detail(exc)

    return result
