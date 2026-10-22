# Chem313 1.0.0-preview.5 — classic desktop, open community preview

This preview replaces the remaining beige with white, black and neutral grey, using compact, square, traditional desktop controls. Completed shape calculations show results first; their instructions can be reopened.

Chem313 organizes the work around four tasks: **Learn, Molecule, Calculate and Records**. Experimental tools stay in Labs, hidden by default. The Mac app has an AppKit sidebar and toolbar; the portable interface follows the same task structure.

- First-launch choices: learn, prepare a calculation, or read an ORCA output.
- One Calculate section, with ORCA or Q-Chem chosen as a setting.
- Persistent molecule context, coordinate-derived identity checks, and visible calculation stages.
- Visible answer cards with immediate feedback and a different-molecule practice task.
- Result cards with plain status, explicit provenance, Eh/kJ/mol/eV units, one primary save action and a downloads menu. NIST CCCBDB is a lookup link; no unmatched reference energy is presented.
- Black-and-white light/dark appearance, optional Qwen help, and a searchable feature/project index.

## Download

**Chem313-1.0.0-preview.5-Mac-arm64.dmg** includes Python and its core scientific libraries. Download, open the disk image and drag Chem313.app to Applications. Apple Silicon, macOS 14+ deployment target; tested on macOS 27. Verify the SHA-256 sums.

This remains an **ad-hoc signed, unnotarized research preview**. macOS may block a downloaded copy. No Developer ID signature or notarization is claimed.

## Verification

The compiled AppKit/WKWebView workflow, core package and native-library audit are checked before publishing. The core performs real bundled RDKit force-field calculations; a separately labelled simulated UI fixture tests result-card presentation without claiming a quantum calculation. See the attached QA record for the checks and scientific limits. Frontend: 42 tests passed. Focused backend: 59 passed.

## Limits

**No real ORCA or Q-Chem quantum calculation has completed here.** Both need a separately licensed installation. ORCA registration is the next step for validating the small water calculation. Force-field calculations do not establish reactions or experimental properties. Qwen is optional, experimental and absent from the core download.

Windows/Linux native CI passed on the previous source candidate ([run 39366818959](https://github.com/jhagir7-arch/chem313/actions/runs/39366818959)). This version's builds are not yet verified there. Their compiled downloads remain withheld pending Microsoft runtime redistribution review on Windows and exact GCC/libquadmath source obligations on Linux. The portable build scripts are included in source.

Use **Chem313-1.0.0-preview.5-Source.zip** for the corresponding source and build scripts. The reviewed source is consolidated into the repository for contribution; the named ZIP is the exact packaged source snapshot. The named source ZIP excludes Git history, private correspondence, research projects, model weights, adapters and training data.

Feedback: [GitHub Issues](https://github.com/jhagir7-arch/chem313/issues). Tell us which step confused you and what you expected to happen. Please omit private research data. No broad scientific or student-usability validation is claimed.

## Community

[Contributor guide](https://github.com/jhagir7-arch/chem313/blob/main/CONTRIBUTING.md) · [Project map](https://github.com/jhagir7-arch/chem313/blob/main/PROJECT_INDEX.md) · [Community guide](https://github.com/jhagir7-arch/chem313/blob/main/docs/COMMUNITY.md). Beginners, educators and chemistry reviewers are welcome. Open an issue with one confusing step or a small reproducible example.
