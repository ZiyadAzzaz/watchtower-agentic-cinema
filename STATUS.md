# WatchTower — submission status

**Date:** September 4, 2026 · **Deadline:** September 9, 2026, 2:00 PM PT
**Live app:** <https://watchtower-283557821298.us-central1.run.app>
**Repository:** <https://github.com/ZiyadAzzaz/watchtower-agentic-cinema>

---

## Am I ready to submit?

**Everything I can build is done. One thing is left, and only you can do it: the video.**

| Requirement | State |
|---|---|
| Hosted project URL, reachable with no credentials | Done |
| Public repository with an open-source license | Done — MIT, detected by GitHub |
| Text description for the submission form | Done — `docs/DEVPOST_SUBMISSION.md` |
| ClickHouse used at runtime via the official MCP server | Done — `mcp-clickhouse==0.4.1`, read-only identity |
| Gemini on Vertex AI via Google ADK | Done — four-stage `SequentialAgent` |
| **Three-minute demo video** | **Not started — yours to record** |

Nothing else blocks submission.

---

## What a judge sees

They open the URL, read the dashboard with no credentials, open the key panel, take the review key,
arm a simulated failure, and **watch four Gemini agents investigate it in real time** — each stage
reporting as it completes — before being asked to approve or dismiss. That whole loop was verified
end to end on the live deployment.

Two independent gates hold at once: **anyone may observe, nobody uncredentialed may control.**
Verified from the open internet — `inject`, `tick`, `approve`, `dismiss`, a wrong key and an empty
key all return `401`.

---

## Health

| | |
|---|---|
| Serving revision | `watchtower-00016-8wg` |
| Tests | 82 passing |
| Lint and format | Clean |
| CI | Green on `cf4a535`, including a real ClickHouse + MCP integration test |
| Incident queue | Clean — zero test artifacts |
| Signal types working | All three: buffer spike, view drop, ad failure |
| Cloud Run | minScale 0, maxScale 1, 1 vCPU, 512 MiB, 120s timeout |

---

## On the published review key

The key `watchtower-judge-demo` is public. That is deliberate, and the risk was measured rather than
assumed:

- It reaches **four endpoints**: arm, advance, approve, dismiss.
- The database identity behind it holds **`SELECT, INSERT` only** — it cannot alter or delete
  anything. Incidents are append-only versioned rows.
- The entire API is **six endpoints**. No SQL passthrough, no secrets route, no file access.
- **No execution tool exists anywhere in the runtime.** A test asserts this.
- Starting an investigation is **rate limited per ten minutes and capped per day**, so a public key
  cannot run up an unbounded model bill. Recording a decision is never limited.
- The key is separate from the operator credential, which stays in Secret Manager.

The worst a bad actor achieves is noise in the queue plus bounded model spend. No data loss is
reachable. If the queue ever looks cluttered before judging, tell me and I will clear it.

---

## What is left, in order

1. **Record the video.** Follow `docs/DEMO_SCRIPT.md`. Warm the URL first — a cold start takes about
   30 seconds. Do one unrecorded rehearsal.
2. **Submit on Devpost.** Paste from `docs/DEVPOST_SUBMISSION.md`; the only placeholder left is the
   video URL.
3. **Read both console spend totals** — Google Cloud and ClickHouse Cloud. No budget alert has fired
   at any checkpoint, but neither exact figure is readable from here.

---

## Known cosmetic issue

GitHub's repository sidebar still lists a second contributor from a stale page cache. Every
authoritative source — the contributors API, the computed stats table, the Insights page, and
commits-by-author — reports **Ziyad Azzaz alone, 11 commits**. A force-push, three new commits and a
visibility toggle all failed to clear it. It expires on its own; the only guaranteed fix is deleting
and recreating the repository, which is your call.

---

## Where to look

| Document | What it covers |
|---|---|
| `README.md` | The product, the architecture, screenshots, how to run it |
| `docs/WALKTHROUGH.md` | Every control on the dashboard, explained |
| `docs/TESTING.md` | Five levels of verification, from a five-second lint to the public deployment |
| `docs/DEVPOST_SUBMISSION.md` | Paste-ready submission text |
| `docs/DEMO_SCRIPT.md` | The three-minute recording runbook |
| `PROJECT_REPORT.md` | Full engineering history, every defect found and fixed |
