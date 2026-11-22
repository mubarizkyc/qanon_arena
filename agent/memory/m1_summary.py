"""M1: Summary memory.

Design (see MEMORY.md for the full rules):
  * write():  after every turn we (a) pin dates / section numbers / case names that
              appear in the USER message (regex, verbatim), and (b) ask the backbone
              model to rewrite a short rolling summary that keeps dates, parties,
              sections and the user's goal, and that replaces any fact the user
              corrected.  The summary is capped at MAX_WORDS words.
  * read():   we return SUMMARY + PINNED FACTS, trimmed to memory_budget_tokens.
              The retrieval hint is the pinned section numbers / case names / dates,
              so BM25 pulls the right statute for a question like
              "which section applies to what I told you earlier?".
  * doc_ids are NOT returned: memory is not a source of citations, only of facts.
"""
from __future__ import annotations

import re

from .base import Memory, MemoryRead, fit_to_budget

# --- fact extractors (kept simple and predictable) -------------------------
MONTHS = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
DATE_RE = re.compile(
    rf"\b\d{{4}}-\d{{2}}-\d{{2}}\b"                      # 2025-03-03
    rf"|\b\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}\b"         # 3/3/2025
    rf"|\b\d{{1,2}}\s+{MONTHS}\s+\d{{4}}\b",             # 3 March 2025
    re.I,
)
SECTION_RE = re.compile(r"\bsections?\s+\d+[A-Z]?(?:\([^)]+\))?\b", re.I)
CASE_RE = re.compile(r"\b[A-Z][\w.']+\s+v(?:s)?\.?\s+[A-Z][\w.']+\b")

SUMMARY_SYS = (
    "You are a memory summariser for a Pakistani legal assistant. "
    "Rewrite the running summary so that it is at most {limit} words and keeps: "
    "(a) every date the user gave, (b) party names and relationships, "
    "(c) section numbers and Act names the user mentioned, (d) the user's goal. "
    "If the user corrected an earlier fact, keep ONLY the corrected version and drop the "
    "old one. Never invent facts, never add legal analysis. "
    "Output only the summary text, with no preamble."
)


class SummaryMemory(Memory):
    code = "M1"
    backend = None          # set by LegalAgent
    seed = 13               # set by LegalAgent
    MAX_WORDS = 120         # hard cap: bounds drift and latency

    def __init__(self):
        self.summary: dict[str, str] = {}
        self.pinned: dict[str, dict] = {}

    # ------------------------------------------------------------------ reset
    def reset(self, session_id):
        self.summary[session_id] = ""
        self.pinned[session_id] = {"dates": [], "sections": [], "cases": []}

    # ------------------------------------------------------------------ read
    def _pinned_block(self, sid: str) -> str:
        p = self.pinned.get(sid) or {}
        parts = []
        if p.get("dates"):
            parts.append("Dates: " + "; ".join(p["dates"][-6:]))
        if p.get("sections"):
            parts.append("Sections: " + "; ".join(p["sections"][-8:]))
        if p.get("cases"):
            parts.append("Cases: " + "; ".join(p["cases"][-4:]))
        return "\n".join(parts)

    def read(self, session_id, query, budget_tokens, count_tokens) -> MemoryRead:
        summary = self.summary.get(session_id, "") or ""
        pinned = self._pinned_block(session_id)

        lines = []
        if summary:
            lines.append("SUMMARY:\n" + summary)
        if pinned:
            lines.append("PINNED FACTS:\n" + pinned)
        text = fit_to_budget(lines, budget_tokens, count_tokens)

        p = self.pinned.get(session_id) or {}
        hint = " ".join(
            (p.get("sections") or [])[-8:]
            + (p.get("cases") or [])[-4:]
            + (p.get("dates") or [])[-3:]
        )
        items = [{"summary": summary, "pinned": p}] if (summary or pinned) else []
        # doc_ids stays empty: memory must not authorise citations
        return MemoryRead(text=text, doc_ids=[], items=items, retrieval_hint=hint)

    # ------------------------------------------------------------------ write
    def _extract(self, text: str):
        return (
            DATE_RE.findall(text or ""),
            SECTION_RE.findall(text or ""),
            CASE_RE.findall(text or ""),
        )

    def _rewrite(self, old: str, user_msg: str, bot_ans: str, cites: str) -> str:
        if self.backend is None:
            return (old + f" User said: {user_msg}").strip()
        sys_prompt = SUMMARY_SYS.format(limit=self.MAX_WORDS)
        user_block = (
            f"OLD SUMMARY:\n{old or '(none)'}\n\n"
            f"NEW USER MESSAGE:\n{user_msg}\n\n"
            f"ASSISTANT ANSWER:\n{bot_ans}\n\n"
            f"CITED DOCUMENTS: {cites or '(none)'}\n\n"
            "Write the updated summary now."
        )
        try:
            raw, _, _ = self.backend.generate(
                [{"role": "system", "content": sys_prompt},
                 {"role": "user", "content": user_block}],
                self.seed,
            )
            return (raw or "").strip()
        except Exception:
            return ""    # caller falls back to append

    def write(self, session_id, turn, user_msg, answer, state):
        # 1) pin facts from the USER message (verbatim, never paraphrased)
        p = self.pinned.setdefault(session_id, {"dates": [], "sections": [], "cases": []})
        dates, sections, cases = self._extract(user_msg)
        for d in dates:
            if d not in p["dates"]:
                p["dates"].append(d)
        for s in sections:
            if s not in p["sections"]:
                p["sections"].append(s)
        for c in cases:
            if c not in p["cases"]:
                p["cases"].append(c)

        # 2) ask the backbone to rewrite the rolling summary
        old = self.summary.get(session_id, "") or ""
        bot_ans = getattr(answer, "answer", "") or ""
        cites = ", ".join(getattr(answer, "citations", []) or [])
        new_summary = self._rewrite(old, user_msg, bot_ans, cites)

        # 3) fallback: if the model failed, append so we never lose data
        if not new_summary:
            new_summary = (old + f" User said: {user_msg}").strip()

        # 4) clamp to MAX_WORDS so drift and cost stay bounded
        words = new_summary.split()
        if len(words) > self.MAX_WORDS:
            new_summary = " ".join(words[: self.MAX_WORDS])
        self.summary[session_id] = new_summary

        return [{
            "turn": turn,
            "summary_words": len(new_summary.split()),
            "pinned_dates": p["dates"][-3:],
            "pinned_sections": p["sections"][-3:],
        }]
