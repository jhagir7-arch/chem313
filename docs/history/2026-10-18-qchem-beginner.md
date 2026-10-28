> Historical design record, not current functionality or a release instruction. See COMMUNITY_HANDOFF.md for present status.

# Beginner Q-Chem preparation implementation plan

Goal: an adult beginning chemistry student chooses water, methane or ethanol, inspects its representations, understands a neutral-singlet HF/def2-SVP single point, and saves an exact reviewable input without code.
Architecture: a dedicated four-step React workflow uses the existing authenticated RDKit operations and deterministic Q-Chem serializer. A bounded offline Qwen topic classifier selects checked contextual guidance; it cannot alter settings or run an engine. A readable project record preserves actual geometry, exact input, learner notes and Qwen provenance.
Tech stack: existing React/TypeScript, FastAPI, RDKit, frozen MLX worker, AppKit/WKWebView. No new dependencies.

Constraints: monochrome academic interface; exact Cartesian input visible; only three supported neutral singlet molecules; force-field geometry distinguished from quantum results; licensed Q-Chem execution not bundled or claimed. Preserve all existing dirty work.

Review focus: changed project or molecule during requests; invalid/blank charge or spin; wrong atom prediction; absent or malformed model response; exported/saved state must match reviewed geometry and settings.

Tasks:
1. Frontend QchemWorkflow.tsx and qchem-workflow.css: choose -> inspect -> settings -> export, keyboard focus and status, beginner checks and corrective feedback, persistent exact project record. Root owns.
2. qchem_coach.py, study_api.py, qwen_worker.py: strict authenticated contextual help, pinned public model, finite schema and grounded explanations; unit tests. Terra owns these files only.
3. App.tsx: default Q-Chem lesson, retain existing ORCA route. qchemStudy.mjs + test: record integrity and readiness checks. Root owns.
4. Real public model prompt checks; frontend/backend tests; build installed preview core and worker, retain model/notices; strict ad-hoc signature verification. Native WKWebView workflow and actual browser downloads/narrow-layout tests; open installed app. Root verifies, update existing improvement plan with actual evidence.

Completed 2026-10-18: installed build21, 36 frontend and29 focused backend tests pass; native water/methane/ethanol plus real Qwen at four steps;12 real-model topic cases and2 compiled FAQ calls; browser downloads, widths1440/760/390, keyboard, explicitly simulated failure/stale responses pass; installed UI1128 andruntime400 hashes checked, license gates and strict ad-hoc signature PASS. Evidence `build/study-agent-preview/qchem-qa/verification.json`. Q-Chem execution and independent usability/faculty validation remain outside the verified preparation slice.
