
# MEMORY.md — Group G03, memory type M1 (Summary memory)

## 1. What our memory stores
Two parts, per session:
- **Summary** — a rolling natural-language paragraph (≤120 words) rewritten by the
  backbone on every turn. Keeps dates, parties, section numbers, Act names and the
  user's goal; replaces any fact the user corrected.
- **Pinned facts** — verbatim strings extracted from USER messages by regex
  (dates, `section N…` mentions, `X v. Y` case names). Append-only; never paraphrased.
Memory holds no retrieved documents and no `doc_ids`.

## 2. Write policy
| Question | Our rule |
| --- | --- |
| What is written to memory? | (a) dates / sections / case names extracted from the user message; (b) the model-rewritten summary |
| When is it written? | Once per turn, in the `memory_write` node, after the answer is generated |
| What is never written? | Retrieved documents, `doc_ids`, the bot's answer text, tool output, our guesses |
| How is an item scored before it is kept? | Pinned facts: kept if regex matches. Summary: kept if non-empty and ≤120 words |
| What happens when the user corrects an earlier fact? | The summary prompt tells the model to replace the old fact; pinned facts are append-only (see §5 example 3) |

## 3. Read policy
| Question | Our rule |
| --- | --- |
| What is read back? | The current summary + the last up to 6 dates / 8 sections / 4 cases in the pinned block |
| How is it ordered / ranked? | Pinned facts are chronological (newest last); the summary is a single block |
| What is dropped first if it does not fit `memory_budget_tokens`? | Oldest pinned dates first, then oldest pinned sections, then the tail of the summary — via `fit_to_budget` |
| What is added to `retrieval_hint`? | Pinned section numbers, case names and dates, so BM25 sees the legal terms even when the user's question does not repeat them |

## 4. State versus memory
`TurnState` holds this turn's retrieved `hits`, `messages` and answer; that is per-turn
and discarded. Memory holds only facts that will be needed in *later* turns.

## 5. Three example conversations

### Example 1 — memory working normally
| Turn | User | Summary / pinned after write | Answer (abridged) |
| --- | --- | --- | --- |
| 1 | "Someone took my laptop from my shop on 3 March 2025." | summary: "User reports a laptop stolen from a shop on 3 March 2025." pinned dates: `["3 March 2025"]` | (acknowledges; no legal section yet) |
| 2 | "I know who did it. It was my neighbour." | summary: "User's laptop was stolen from a shop on 3 March 2025; neighbour is the suspected taker." | (acknowledges) |
| 3 | "We tried to settle but it didn't work." | summary: "...; informal settlement attempted and failed." | (acknowledges) |
| 4 | "I still have the receipt." | summary: "...; user has the purchase receipt." | (acknowledges) |
| 5 | "Based on what I told you, which PPC section applies?" | — | "Section 379 of the Pakistan Penal Code, 1860 (Punishment for theft)…" `citations: ["PPC-379"]` |

Retrieval on turn 5 is helped by `retrieval_hint = "3 March 2025"`, but the fact that
this is a **shop theft** comes from the summary — M0 (2-turn window) cannot see turns 1–3.

### Example 2 — the user corrects a fact
| Turn | User | Memory after write |
| --- | --- | --- |
| 1 | "My car was taken on 4 March 2025." | summary: "...car taken 4 March 2025" pinned dates: `["4 March 2025"]` |
| 2 | "Actually it was 5 March, not 4 March." | summary: "...car taken **5 March 2025** (user corrected: not 4 March)" pinned dates: `["4 March 2025", "5 March 2025"]` |
| 3 | "Which Contract Act section applies to the bailee?" | Answer cites `CA-151`; the summary has the correct 5 March date. |

The summary is the source of truth for dates; pinned facts stay append-only, so if a
date is wrong the summary still has the correction. (This is our known trade-off.)

### Example 3 — a case where our memory still fails
| Turn | User | Memory after write |
| --- | --- | --- |
| 1 | "Section 420 PPC is relevant to me." | pinned sections: `["section 420"]` |
| 2–6 | unrelated chat | summary grows; word cap hit; some detail rolls off |
| 7 | "Which PPC section did I mention at the start?" | Answer may say "section 379" from a wrong retrieval; the pinned block still has `section 420`, but the summary no longer mentions the context, so the bot may pick the wrong one. |

Root cause: the summary is one flat paragraph; when it hits the 120-word cap, older
context can roll off. Pinned facts catch **section numbers and dates**, but not the
*surrounding context* that tells us which section belongs to which scenario.
</｜｜DSML｜｜ parameter>
</｜｜DSML｜｜ invoke>
</｜｜DSML｜｜ calls>
