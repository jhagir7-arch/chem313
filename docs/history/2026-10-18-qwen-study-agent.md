> Historical design record, not current functionality or a release instruction. See COMMUNITY_HANDOFF.md for present status.

# Qwen molecule-study agent implementation plan

Goal: make a real, bounded local chemistry study accessible from an ordinary question.
Architecture: typed offline Qwen planner -> independent catalog/capability validation -> immutable project-bound plan -> finite RDKit worker -> content-addressed project records -> accessible study screen -> existing ORCA input review.
Tech stack: existing FastAPI/Python/RDKit, React/TypeScript, AppKit/WKWebView, frozen MLX Qwen worker. No new runtime dependency.
Spec: 2026-10-18-qwen-study-agent-spec.md


## Constraints and review focus


Likely failures: model changes identity/count; unsupported reaction misrouted to shapes; stale project/prompt results; cancellation races or unbounded sampling; packaged worker/model differs from tested source.

## Tasks

1. Sampling adapter and focused tests: study_sampling.py, test_study_sampling.py. Validate graph scope, deterministic seeds, energy compatibility, deduplication and cancellation.
2. Qwen worker study mode with three-field output and provenance; preserve legacy drafting. Real public-model prompt checks.
3. Root study_agent.py and study_api.py: immutable expiring single-use plans, one active bounded job, snapshots/cancel, project storage, grounded lesson/summary. Register in desktop.py.
4. StudyAgent.tsx and study-agent.css: plain question/examples, review/Run, keyboard status/progress/cancel, 3D/table/all outcomes, exports, ORCA handoff. Root App.tsx integration.
5. Independent science, controller, accessibility and packaging reviews/tests. Research and truth-check launch drafts without sending.
6. Run focused backend/frontend checks, real Qwen study cases and headless browser workflow. Rebuild core and public worker, assemble pinned public model with licenses, verify ad-hoc signature. Run actual native workflow with isolated data and retain evidence. Open verified compiled app.

Success: real Qwen routes supported prompts to independently checked studies, real RDKit outcomes and saved bytes match display/handoff; unsupported and stale requests cannot execute; compiled app passes the same flow offline. Report actual limits and remaining external-engine gaps.
