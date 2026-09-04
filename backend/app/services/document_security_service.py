from __future__ import annotations

import uuid
from dataclasses import dataclass


PRIVATE_CACHE_CONTROL = "private, no-store, max-age=0"
PRIVATE_RESPONSE_HEADERS = {
    "Cache-Control": PRIVATE_CACHE_CONTROL,
    "Pragma": "no-cache",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


@dataclass(frozen=True)
class ProcessingBudget:
    allowed: bool
    retry_after: int


async def consume_processing_budget(pool, *, user_id: str, limit: int, window_seconds: int):
    # One atomic upsert serializes same-user requests across backend replicas.
    # Saturation bounds counters under sustained denial; rejected requests do
    # not extend the current window.
    row = await pool.fetchrow(
        """
        insert into document_processing_limits (user_id, request_count, expires_at)
        values ($1, 1, now() + make_interval(secs => $3::double precision))
        on conflict (user_id) do update set
          request_count = case
            when document_processing_limits.expires_at <= now() then 1
            else least(document_processing_limits.request_count + 1, $2::integer + 1)
          end,
          expires_at = case
            when document_processing_limits.expires_at <= now()
              then now() + make_interval(secs => $3::double precision)
            else document_processing_limits.expires_at
          end
        returning request_count <= $2 as allowed,
          greatest(1, ceil(extract(epoch from (expires_at - now()))))::integer as retry_after
        """,
        uuid.UUID(user_id),
        limit,
        float(window_seconds),
    )
    if not row:
        raise RuntimeError("Processing budget was not recorded.")
    return ProcessingBudget(bool(row["allowed"]), int(row["retry_after"]))
