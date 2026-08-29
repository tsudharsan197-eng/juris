# Juris AI Collaboration Instructions

These instructions apply to every AI or human collaborator working in this repository.

## Start Every Session

1. Read `MEMORY.md` for current product and architecture context.
2. Read `docs/DECISIONS.md` when changing architecture, security, data flow, AI behavior, or deployment.
3. Read `docs/PROJECT_RECOVERY.md` before backup, restoration, migration, or destructive Git work.
4. Run `git status --short` and inspect the relevant code before editing.
5. Treat conversation history as helpful context, not as a substitute for the current repository.

## Maintain Project Memory

- Update `MEMORY.md` in the same commit when durable routes, architecture, dependencies, commands, invariants, deployment requirements, or known production caveats change.
- Keep `MEMORY.md` concise and current. It is a state snapshot, not a session transcript.
- Record significant architectural choices in `docs/DECISIONS.md` using the existing decision format.
- Do not write secrets, tokens, credentials, private uploaded documents, raw confidential OCR output, or personal data into memory files.
- Do not record speculative plans as completed facts.

## Git Safety

- Preserve unrelated user changes and inspect a dirty worktree before editing.
- Stage explicit paths; never use a broad add when generated artifacts or private files may be present.
- Do not use destructive Git commands unless the user explicitly requests them.
- A local commit is not an off-device backup. Push important checkpoints to the configured remote.
- Never commit `.env`, OCR debug output, private PDFs, database dumps containing user data, or credentials.

## Verification

Run checks appropriate to the changed surface:

```bash
python3 -m py_compile backend/app/main.py
cd backend && python -m pytest -q
npm run build
./scripts/verify-project-memory.sh
```

Frontend changes should also be verified in the browser at relevant desktop and mobile sizes. Backend changes touching auth, ownership, caching, OCR, RAG, or schemas require focused tests in addition to compilation.
