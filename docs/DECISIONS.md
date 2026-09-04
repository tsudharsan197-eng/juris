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

## ADR-007: External-object deletion is ledger-backed and reconciled

- Date: 2026-08-29
- Status: Accepted

**Context:** R2 object deletion and Postgres row deletion cannot share one atomic transaction. Upload or delete failures between those systems can otherwise create untracked private objects or metadata that falsely implies deletion succeeded.

**Decision:** Juris writes document metadata before attempting an upload and compensates any uncommitted storage attempt. User deletion records a durable `r2_deletion_jobs` row before touching R2, confirms the object deletion, and only then removes the document row in the same database transaction that completes the job. A background worker retries recorded failures and runs report-only reconciliation. Unknown historical objects are never removed automatically.

**Consequences:** Migration `010_r2_lifecycle_security.sql` must be applied before this backend release. Reconciliation output contains counts and truncated SHA-256 key fingerprints rather than confidential filenames. The ledger improves consistency but is not a backup; R2 and Supabase still require independent recovery copies and tested restore procedures.

**2026-09-04 refinement:** Upload rollback also records intent before R2 deletion. Duplicate requests preserve active leases and backoff; attempt numbers fence stale finalization. Retry polling is separate from daily reconciliation. Pending deletes return 503 until storage and metadata cleanup both complete, preserving truthful behavior in the existing client. The in-process worker requires a running service; it is not an external scheduled job.

## ADR-008: Shared processing budgets and private file responses

- Date: 2026-09-04
- Status: Accepted

**Context:** Per-process throttles reset on restart and multiply with replicas. Multipart parsing happens before FastAPI upload dependencies, so application quotas alone cannot bound upload spool storage. Private signed URLs also require explicit caching and disposition controls.

**Decision:** Upload and reprocess share an atomic Postgres quota keyed by verified user identity. Quota failure is fail-closed, with Retry-After preserved through the existing error envelope. A multipart body ceiling bounds declared-length and chunked requests before processing. Private API responses, new objects, and signed GET overrides use no-store. Filenames are sanitized, PDF previews remain inline, and Word files download as attachments. Remove the temporary public OpenAI diagnostic.

**Consequences:** Migration 011 must precede the P1 backend deployment. Existing R2 objects need no metadata rewrite for newly generated signed URLs. Account quotas and per-request byte limits are not a global concurrency, anti-bot, or DDoS defense; provider-level controls and monitored capacity remain necessary. No-store cannot revoke previously downloaded copies or previously issued URLs.

## ADR-009: Security operations distinguish failure from missing evidence

- Date: 2026-09-04
- Status: Accepted

**Context:** Local security patches and healthy API responses do not prove production migrations, storage consistency, provider privacy, or recovery readiness. A monitor that treats inaccessible checks as passing creates false confidence.

**Decision:** Provide a read-only CLI with explicit pass/fail/warn/unknown findings and distinct nonzero exits. Inspect effective privileges, deletion backlog, bounded R2 inventory, and optional unauthenticated HTTP behavior without downloading private content or invoking legacy OpenAI diagnostics. Keep provider-only controls unknown until independently verified. Regression CI runs without production credentials, using pinned actions and disposable SQL fixtures.

**Consequences:** P2 adds no migration or new public endpoint. The Docker image packages operational scripts and excludes private build-context files. Production deployment, external scheduling/alert delivery, backup/restore verification, token review, and capacity controls remain separate release gates, not completed facts.
