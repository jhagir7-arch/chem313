> Historical design record, not current functionality or a release instruction. See COMMUNITY_HANDOFF.md for present status.

# Beginner molecule workflow implementation plan


**Goal:** A first-time user can choose a named molecule, compare generated starting shapes offline, understand the result, and prepare an input without Qwen or SMILES knowledge.

**Architecture:** Reuse the existing validated RDKit conformer action with five fixed seeds. Bind results to a project and exact editor molecule, rank only compatible force-field energies, and retain the selected SDF for the existing ORCA review/save flow. A dismissible guided panel supplies vocabulary and concrete next actions; the editor stays available.

**Tech stack:** Existing React/TypeScript UI, RDKit core, Node tests, Playwright and the existing compiled Mac runtime.

**Design:** White (#ffffff), paper (#ededed), ink (#151515), muted (#555555), rule (#d4d4d4). System sans controls, restrained existing serif section titles, monospace numerical data. One task worksheet above the molecule canvas with numbered actionable steps, a ranked shape table, and no chat dependency. On narrow screens, stages stack and the result table scrolls. Keyboard controls use visible labels and focus outlines.

**Constraints:** No added dependencies. No claim of unique conformers or a global minimum. Force-field energy is not quantum energy or experimental evidence. Never compare different molecular identities or force fields. Drawing/project changes invalidate selection/export/preparation. Preserve unpublished/release work and existing scientific review gates.

**Review focus:** Invalid molecule; all or partial conformer generation failure; drawing/project changed during sampling; duplicate shapes; limited screen width/keyboard use.

## Tasks

- [x] Add deterministic example catalog and validated ranking helper with tests for finite energies, same model/identity, ordering, zero-relative reference, ties and failed candidates.
- [x] Add guided worksheet with explicit replacement confirmation, five-shape sampling, valid-only selection/export, plain explanations and honest limits; invalidate stale work on graph/project changes.
- [x] Improve ORCA setting descriptions and provide a direct route back to the structure editor when geometry is absent.
- [x] Run frontend tests/build and browser workflow against the real core, including invalidation, save/download equivalence and responsive/keyboard checks.
- [x] Prepare a separate compiled local preview with the updated packaged UI, verify signatures and run the beginner workflow using the compiled runtime. Preserve the public release.
