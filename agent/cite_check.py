"""Runtime citation monitor (Step 4, item 2).

Policy chosen: "Dropped".
If the model cites a document that was not in the retrieved context or memory
(i.e., it hallucinated a section or case), we remove that citation from the
final answer before it is shown to the user or scored.
"""
from __future__ import annotations

def check(answer, allowed_ids: set[str], corpus) -> tuple[object, dict]:
    allowed_base = {a.split("@")[0] for a in allowed_ids}

    # 1. Identify hallucinated / ungrounded citations
    ungrounded = [
        c for c in answer.citations
        if c not in allowed_ids and c.split("@")[0] not in allowed_base
    ]

    # 2. Apply policy: Drop the bad citations
    if ungrounded:
        answer.citations = [c for c in answer.citations if c not in ungrounded]
        action = "dropped"
    else:
        action = "none"

    flags = {
        "ungrounded": ungrounded,
        "n_ungrounded": len(ungrounded),
        "action": action,
    }
    return answer, flags
