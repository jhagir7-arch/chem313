# Accessible local molecule-study agent

Historical specification from 2026-10-18. This describes the earlier shell, not the v2 desktop app.

The primary screen accepts a plain-language question. A local, pinned public Qwen model proposes a small typed task. Independent validation resolves a supported named molecule, preserves explicit sample counts, and rejects unsupported reaction/clinical claims. The user sees the structure identity and bounded plan before Run. Unknown names ask for clarification rather than invented SMILES.

Supported execution: one neutral closed-shell small molecule, one to eight fixed-seed ETKDG/MMFF-or-UFF samples, duplicate removal by symmetry-aware heavy-atom RMSD at 0.25 angstrom, compatible force-field energy ranking. Cancellation stops scheduling and retains completed results. This is neither exhaustive conformational search nor a quantum or experimental result.

Ethanol/water is a sourced teaching illustration, distinct from calculations. The model supplies no unchecked scientific prose. Medication breakdown and unknown reaction prediction are unsupported.

A run saves exact prompt, immutable plan, model provenance, seeds, engine versions, every outcome, selected SDF hashes, and grounded summary in the existing project store. Selected geometry transfers unchanged into the checked ORCA input workflow. ORCA remains a separate installation.

Keyboard access, visible focus, status announcements, readable errors, small-screen reflow, and text alternatives are acceptance criteria. Verify unit/controller checks, real local Qwen cases, browser interaction, and the rebuilt compiled Mac app. External launch actions stay staged until specific content and destinations are approved.
