# Preview 2 verification

Tested on an Apple Silicon Mac running macOS 27. Minimum declared system: macOS 26.2. Other systems have not been tested.

- Backend: 160 tests plus 7 subtests passed; frontend: 19 tests passed.
- Compiled AppKit/WKWebView workflow passed: offline base Qwen water draft, explicit Apply, Ketcher editing, structure-preserving Fit, saved structure, RDKit geometry, reviewed and saved ORCA input, numerical recipes, CSV fitting, SVG rendering, synthetic ORCA result review and artifact integrity.
- Frozen service passed with fresh HOME, relocated working directory and PATH restricted to system tools: real Qwen water/ethanol drafts and ambiguity/conflict checks, numerical references, persistence and integrity. No external Python or Node used.
- All 300 unique Mach-O files are arm64, have deployment targets within macOS 26.2 and passed the binary audit.
- Core and Qwen native ownership/license notice gates, pinned model file hashes, internal symlink checks and strict ad-hoc code-signature verification passed.

This is workflow and packaging verification, not an independent chemistry benchmark. No licensed ORCA calculation was executed. ORCA, Avogadro, PySCF and tblite are not bundled. The model is the upstream 4-bit base model, without the private fine-tuned adapter or datasets.

The app is not Developer ID signed or notarized. Gatekeeper first-launch acceptance is not claimed.
