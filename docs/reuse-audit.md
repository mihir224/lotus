# Preliminary reuse audit

Audit date: 2026-10-13

This is the Phase 0 assessment of the supplied local repositories. The product
owner directed Lotus to reuse ideas and behavior only, with all implementation
written from scratch. No source is copied into Lotus.

## Repository baselines

| Repository | Revision inspected | Working tree | License found | Baseline tests |
|---|---|---|---|---|
| AudLook | `81546ff36a1c022802e0430e79ac787e0d3795a1` | clean `main` | No | Not run: `pytest` is not installed in the active environment |
| VidScribe | `14ef9fefff9231a6d9d8a669c4cd722f5f1b1618` | clean `main` | No | Not run: dependencies are not installed (`tsc` missing) |
| defect-triage-orchestrator | `12f16558dba1394ef063999e5b53f856ada85786` | `deployment` matches origin; modified `.DS_Store` and submodule state remain | No | 50 backend tests passed |
| edmx-schema-analyzer submodule | `c6dc8443d1e9b30b2c1ff203a3860200b8a8a650` | pinned submodule | No license observed | Not independently run |

## Candidate modules

| Source | Module or behavior | Original dependencies | Proposed action | Google-only gap | Tests to add in Lotus | Expected saving |
|---|---|---|---|---|---|---|
| defect-triage-orchestrator | React/Vite/Tailwind layout and progressive task UI | React, Vite, Tailwind, Framer Motion | Adapt after license confirmation | Remove ticket-specific coupling and write controls | Route chip, evidence drawer, task drawer, accessibility | High |
| defect-triage-orchestrator | FastAPI app/config/logging conventions | FastAPI, Pydantic | Adapt after license confirmation | Replace AWS and direct provider configuration | Config validation, redaction, correlation IDs | Medium |
| defect-triage-orchestrator | SSE workflow progress contract | FastAPI SSE, React fetch stream | Reference or adapt | Replace LangGraph node model with ADK task events | split-frame parser, reconnect, ordered events, cancellation | High |
| defect-triage-orchestrator | Jira/Confluence clients and normalization | HTTP/MCP, direct Jira fallback | Reference only | Use narrow read-only MCP adapters; remove direct writes | allowlist, byte caps, schema errors, auth failures | Medium |
| defect-triage-orchestrator | Existing router/orchestrator | LangGraph, LangChain, Bedrock | Reject direct reuse | Rebuild in Google ADK; remove Bedrock/LangChain/Milvus | structured routing, exact-ID rules, injection negatives | Low |
| VidScribe | Shared Zod note/job contracts | TypeScript, Zod | Adapt concepts after license confirmation | Replace video-note schema with meeting schema | schema parity, partial failures, progress validation | High |
| VidScribe | Timestamped caption chunking with overlap | TypeScript | Adapt algorithm after license confirmation | None; change token sizing and meeting boundaries | ordering, overlap, empty cues, stable IDs | Medium |
| VidScribe | Async in-memory job lifecycle | TypeScript, Fastify | Reference only | Persist with Firestore and dispatch with Cloud Tasks | leases, idempotency, retries, terminal states | Medium |
| VidScribe | Visual-frame request model | Browser APIs, Sharp | Reference only | Upload to Cloud Storage and analyze with Gemini | limits, media validation, timestamp evidence | Medium |
| VidScribe | Note generation provider | AWS Bedrock | Reject | Replace with Gemini on Vertex AI | schema validation and bounded repair | Low |
| AudLook | Timestamped word normalization and utterance building | Python, Pydantic | Adapt after license confirmation | Generalize fixed two-speaker constraint | monotonic timestamps, unknown speakers, long turns | High |
| AudLook | Meeting/transcript chunk construction | Python | Adapt algorithm after license confirmation | Tune to PRD token and time windows | boundary, overlap, short-tail merge | High |
| AudLook | Hybrid candidate merge and RRF utilities | Python, PostgreSQL/pgvector | Adapt concepts | Implement against BigQuery; remove local model stack | dedupe, stable rank, ACL filter invariants | Medium |
| AudLook | Retrieval evaluation fixtures and metrics | Python, YAML | Adapt structure after license confirmation | Point at Lotus source IDs and BigQuery/fakes | Recall@5, MRR, abstention, isolation | High |
| AudLook | Gemini transcription adapter | Gemini Developer API key and hosted file upload | Reference only | Use Vertex AI/ADC or Speech-to-Text; configurable model | timestamps, cleanup, provider errors | Medium |

## Security and data-flow findings

- The triage repository tracks `UI/frontend/.env`, which contains a real-looking
  bearer token. Treat it as compromised: revoke/rotate it and remove it from the
  current tree and Git history as appropriate. Lotus ignores all `.env*` files
  except `.env.example`.
- The triage project includes direct Jira REST configuration, a Jira comment
  write path, AWS Bedrock, LangGraph/LangChain, Milvus, Kibana, and multiple MCP
  services. None should cross into the Lotus execution path unchanged.
- The triage checkout is current at the pinned revision above, but local
  `.DS_Store` and submodule changes remain and are excluded from reference work.
- VidScribe contacts YouTube and AWS Bedrock. Its in-memory task store is useful
  only as a behavioral reference; it does not satisfy durability or tenancy.
- AudLook uses Gemini API-key authentication, local Hugging Face models,
  PostgreSQL/pgvector, and bundled audio whose redistribution rights are not
  documented. The audio must not be copied without permission.
- No committed cloud access keys were observed in AudLook or VidScribe from the
  targeted environment/provider scan. This was not a full forensic secret scan.

## Provenance decision

Reference repositories are behavioral inputs only. Lotus uses new code and does
not copy implementation, bundled media, or repository assets from them.
