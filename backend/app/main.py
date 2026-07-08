import asyncio
import io
import math
import os
import re
import traceback
import uuid
import zipfile
from datetime import datetime
from typing import Annotated

import asyncpg
import boto3
import httpx
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from google import genai
from google.genai import types
from pypdf import PdfReader
from pydantic import BaseModel

load_dotenv()

MAX_FILE_SIZE = 25 * 1024 * 1024
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
EMBEDDING_BATCH_SIZE = 64
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768
ANSWER_MODELS = ("gemini-2.5-flash", "gemini-1.5-flash")
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
    database_url = os.getenv("DATABASE_URL")
    app.state.db_pool = await asyncpg.create_pool(database_url) if database_url else None


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
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not verify auth token with Supabase.",
        ) from exc

    if response.status_code != 200:
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


async def generate_embeddings(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    if not texts:
        return []

    api_key = get_env("GEMINI_API_KEY")
    embeddings = []

    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[start:start + EMBEDDING_BATCH_SIZE]
        batch_embeddings = await asyncio.to_thread(generate_gemini_embeddings_batch, api_key, batch, task_type)
        if len(batch_embeddings) != len(batch):
            raise RuntimeError("Gemini embeddings response count did not match chunk count.")
        embeddings.extend(batch_embeddings)

    if len(embeddings) != len(texts):
        raise RuntimeError("Gemini embeddings response count did not match chunk count.")
    if any(len(embedding) != EMBEDDING_DIMENSIONS for embedding in embeddings):
        raise RuntimeError("Gemini embeddings response dimensions did not match document_chunks.embedding.")
    return embeddings


def generate_gemini_embeddings_batch(api_key: str, texts: list[str], task_type: str) -> list[list[float]]:
    client = genai.Client(api_key=api_key)
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=EMBEDDING_DIMENSIONS,
        ),
    )
    return [normalize_embedding(embedding.values) for embedding in result.embeddings]


async def generate_answer(prompt: str) -> str:
    api_key = get_env("GEMINI_API_KEY")
    return await asyncio.to_thread(generate_gemini_answer, api_key, prompt)


def generate_gemini_answer(api_key: str, prompt: str) -> str:
    client = genai.Client(api_key=api_key)
    last_error = None
    for model in ANSWER_MODELS:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=700,
                ),
            )
            answer = getattr(response, "text", "") or ""
            return answer.strip()
        except Exception as exc:
            last_error = exc

    raise RuntimeError(f"Gemini answer generation failed: {last_error}") from last_error


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
                      document_id, user_id, chunk_index, chunk_text, embedding, created_at
                    )
                    values ($1, $2, $3, $4, $5::vector, now())
                    """,
                    [
                        (document_uuid, user_uuid, index, chunk, vector_literal(embeddings[index]))
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
    user_id: str,
    question_embedding: list[float],
    limit: int = 5,
):
    return await pool.fetch(
        """
        select chunk_index, chunk_text
        from document_chunks
        where document_id = $1
          and user_id = $2
          and embedding is not null
        order by embedding <=> $3::vector
        limit $4
        """,
        uuid.UUID(document_id),
        uuid.UUID(user_id),
        vector_literal(question_embedding),
        limit,
    )


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
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    document = await get_owned_document(pool, document_id, user_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    question_embedding = (await generate_embeddings([question], task_type="RETRIEVAL_QUERY"))[0]
    chunks = await search_document_chunks(
        pool=pool,
        document_id=document_id,
        user_id=user_id,
        question_embedding=question_embedding,
        limit=5,
    )

    if not chunks:
        return AskDocumentResponse(
            answer="I could not find that information in this document.",
            sources=[],
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
