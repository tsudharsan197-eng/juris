# Juris Architecture Decisions

This is an append-only record of durable product and engineering decisions. Supersede old decisions with a new entry instead of silently rewriting history.

## Decision Template

```text
## ADR-NNN: Short title

- Date: YYYY-MM-DD
- Status: Accepted | Superseded by ADR-NNN

Context

Decision

Consequences
```

## ADR-001: OpenAI-only runtime AI

- Date: 2026-08-29
- Status: Accepted

**Context:** Juris previously carried historical embedding migration references to other providers, while the production system needs one observable and supportable AI path.

**Decision:** Runtime chat, analysis, Compass, and embeddings use the OpenAI API through `OPENAI_API_KEY`. Historical Ollama migration files may remain for migration history, but no Gemini or Ollama runtime path should be reintroduced without a new decision.

**Consequences:** Model configuration is centralized in backend environment variables. OpenAI errors must retain actionable status and provider messages without exposing secrets.

## ADR-002: Document intelligence remains source-grounded

- Date: 2026-08-29
- Status: Accepted

**Context:** Legal-document answers become unsafe and less useful when generated without evidence from the owned document.

**Decision:** Document Chat and generated document analyses use stored page-aware text/chunks and preserve source references. Juris Compass remains a separate legal-research system and never receives document chunks or a document ID.

**Consequences:** Retrieval quality, page metadata, and ownership checks are product-critical. Unsupported details must not be fabricated to fill missing OCR or retrieval context.

## ADR-003: Hybrid native extraction and bounded local OCR

- Date: 2026-08-29
- Status: Accepted

**Context:** Native PDF parsers fail on scanned or partially scanned legal documents, while OCRing every page wastes resources and can reduce clean-text quality.

**Decision:** Extract native text first and OCR only unreadable or incomplete pages. OCR runs locally with Tesseract using bounded multi-pass scoring, preprocessing, orientation, and DPI retries.

**Consequences:** Render uses the backend Dockerfile to install Tesseract. Reprocessing invalidates stale text, chunks, embeddings, and generated analyses. Debug OCR content stays development-only.

## ADR-004: Cache generated analyses, not document chat

- Date: 2026-08-29
- Status: Accepted

**Context:** Reopening AI tools should be fast and should not repeatedly spend tokens for unchanged documents, while user questions are live and question-specific.

**Decision:** Cache Executive Summary, Document Intelligence, Clause Intelligence, Risk Analysis, and Compare in `ai_outputs` using content/version-aware hashes. Do not globally cache document Chat questions.

**Consequences:** Document changes and reprocessing must change or invalidate hashes. Compare hashes include both documents and their version state.

## ADR-005: Workspace uses one intentional content scroller

- Date: 2026-08-29
- Status: Accepted

**Context:** Competing page, report, and sidebar scroll owners caused clipped reports and unstable application behavior.

**Decision:** The processed-document desktop workspace is a `100dvh` application shell. The top context and taskbar remain stationary, and the active tool viewport owns vertical scrolling. Chat may have a message scroller while keeping its composer available.

**Consequences:** Grid and flex children require correct `min-height: 0` and `min-width: 0`. Lenis must not hijack workspace-native scrolling. Long Executive Summary output must remain reachable to its true bottom.

## ADR-006: Private ownership is enforced at every data boundary

- Date: 2026-08-29
- Status: Accepted

**Context:** Juris stores private legal documents and generated intelligence across Supabase, R2, and OpenAI-backed processing.

**Decision:** Backend document operations require a valid Supabase Bearer token and verify document ownership. R2 remains private, and frontend code receives only public Supabase configuration.

**Consequences:** Ownership checks cannot be traded for convenience. Secrets remain backend-only, and deletion/reprocessing must preserve user isolation.
