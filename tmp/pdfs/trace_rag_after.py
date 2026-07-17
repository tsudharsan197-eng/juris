from __future__ import annotations

import asyncio
import json
import math
import os
import sys
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "backend/.env", override=True)
sys.path.insert(0, str(ROOT / "backend"))

from app import main as backend
from app.services.document_processing_service import (
    build_page_aware_chunks,
    validate_chunk_coverage,
)
from app.services.pdf_extraction_service import PageExtraction


QUESTIONS = (
    "Who are the parties to this agreement?",
    "What type of document is this?",
    "What are the lease start and end dates?",
    "What is the monthly rent and when is it due?",
    "What is the security deposit?",
    "What is the notice period?",
    "When can the lease be terminated?",
    "Can the tenant sublet the premises?",
    "What are the tenant's main obligations?",
    "What are the important clauses?",
    "What obligations and signatures appear on the final page?",
)


def cosine_distance(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_length = math.sqrt(sum(value * value for value in left))
    right_length = math.sqrt(sum(value * value for value in right))
    return 1.0 - numerator / max(1e-12, left_length * right_length)


async def main() -> None:
    root = ROOT / "tmp/pdfs/ocr-after"
    metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    pages = []
    for details in metadata:
        page_number = details["page_number"]
        page_values = {key: value for key, value in details.items() if key != "characters"}
        pages.append(
            PageExtraction(
                text=(root / f"page-{page_number}.txt").read_text(encoding="utf-8"),
                **page_values,
            )
        )

    chunks = build_page_aware_chunks(pages, chunk_size=backend.CHUNK_SIZE, overlap=backend.CHUNK_OVERLAP)
    validate_chunk_coverage(pages, chunks)
    embeddings = await backend.generate_embeddings([chunk.text for chunk in chunks])
    question_embeddings = await backend.generate_embeddings(list(QUESTIONS), task_type="RETRIEVAL_QUERY")

    results = []
    for question, question_embedding in zip(QUESTIONS, question_embeddings, strict=True):
        ranked = sorted(
            (
                (cosine_distance(question_embedding, embedding), chunk)
                for chunk, embedding in zip(chunks, embeddings, strict=True)
            ),
            key=lambda item: item[0],
        )[:3]
        rows = [
            {
                "chunk_index": chunk.chunk_index,
                "chunk_text": chunk.text,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "extraction_method": chunk.extraction_method,
                "ocr_confidence": chunk.ocr_confidence,
                "distance": distance,
            }
            for distance, chunk in ranked
        ]
        results.append(
            {
                "question": question,
                "chunks": [
                    {
                        "chunk_index": row["chunk_index"],
                        "page": row["page_start"],
                        "distance": round(row["distance"], 5),
                        "preview": backend.chunk_preview(row["chunk_text"]),
                    }
                    for row in rows
                ],
            }
        )
        print(
            json.dumps(
                {
                    "question": question,
                    "chunks": [row["chunk_index"] for row in rows],
                    "pages": [row["page_start"] for row in rows],
                }
            )
        )

    output = ROOT / "tmp/pdfs/rag-after.json"
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
