> Historical design record, not current functionality or a release instruction. See COMMUNITY_HANDOFF.md for present status.

# Research Workspace Implementation Plan


**Goal:** Make molecule building, calculation preparation and reproducible local research operations usable in a compact monochrome desktop application.

**Architecture:** Retain the AppKit/WKWebView shell, local core and isolated workers. Add a fixed native command bridge, persistent research views and declarative recipes over the existing reviewed job API. Qwen remains an experimental local draft assistant; licensed ORCA remains a separate configured executable.

**Tech Stack:** Swift/AppKit, React/TypeScript, existing Python scientific workers.


## Design

White drawing surface, light gray instrument chrome, dark text and rules. Colors: #151515, #555555, #9a9a9a, #d4d4d4, #ededed, #ffffff. Sans-serif controls, monospaced units/source/identifiers, serif confined to scientific reading if useful. Compact project rail, workflow toolbar, large drawing surface and inspector, optional Qwen pane. No marketing headline or dashboard card grid.

## Work and proof

- [x] Native menus: File/Edit/View/Calculation/Window/Help, responder editing, fixed command bridge, zoom and window controls. Compile Swift and invoke actual menu actions.
- [x] Research workspace: compact navigation and persistent preparation/job views, visible structure→geometry→input→results path, Qwen dock, help with workflow and capability limits. Test at 1440 and minimum supported width.
- [x] Reproducible scripting: versioned JSON recipe source, strict allowlist, complete preview before sequential execution, immutable existing job records, explicit cancellation and failure stop. Test parsing and run real conversions/statistics through UI.
- [x] Engine verification: run all current adapters through the frozen core/workers with numerical reference and artifact hash checks; retest Avogadro transfer and Qwen→saved input. Report actual ORCA availability separately.
- [x] Build 0.8.0, sign, package, install side-by-side, run native workflow and menu verification. Preserve receipts and a concise checkpoint.

## Review focus

- Changed drawings must invalidate geometry/settings assumptions; earlier checks cannot authorize changed input.
- Switching views must retain saved input, running job and Qwen draft state.
- Recipe edits/project changes must invalidate approvals and prevent later steps from being scheduled against stale context.
- Missing ORCA and Qwen rejection must remain visible, actionable states.
- Native editing shortcuts must respect text/editor focus; no unrestricted bridge evaluation from document content.
