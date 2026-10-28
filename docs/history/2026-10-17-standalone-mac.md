> Historical design record, not current functionality or a release instruction. See COMMUNITY_HANDOFF.md for present status.

# Standalone Mac Implementation Plan

**Goal:** A downloadable Apple Silicon OpenChem app runs its chemistry workbench without a user installing Python, Node, or dependencies.
**Architecture:** Freeze the current core and prebuilt UI with PyInstaller. Use one bundled engine executable for the local service and restricted scientific subprocesses. A package profile restricts advertised operations to included engines and carries version identities; omit private models, unrelated workers and uncleared assets.
**Tech stack:** Swift/AppKit/WKWebView, frozen Python, built React/Ketcher/3Dmol UI, RDKit/NumPy/SciPy/Matplotlib.

## Constraints and review focus
- Apple Silicon only. Derive minimum OS from every included Mach-O and wheel; never claim macOS 14 compatibility if a wheel requires newer.
- No user Python/Node, shell download/install step, local checkout, model assets or private source receipts at runtime.
- Relocated app and paths containing spaces work; environment cannot redirect bundled workers to development runtimes.
- Unavailable engines fail before creating a job; catalog distinguishes included, installed and tested.
- Retain exact molecular source/input/report bytes, explicit approval, bounded workers and cancellation.
- Developer ID/notarization are separate release gates; no identity currently available.

## Tasks
1. Add `runtime_profile.py`, restrict `science_jobs.py` and standalone registry, dispatch `--science-worker` in `desktop/service.py`. Add regression tests for two allowed operations, unavailable-operation refusal, frozen paths and source-mode compatibility. Update UI availability/copy/default recipe for included core.
2. Add `scripts/build_standalone_app.sh`, license inventory and standalone README/build instructions. Freeze core/UI, copy audited notices, compile native shell, strict sign, archive and DMG. Keep old private build untouched. Check output has no external paths/model assets and all native libraries resolve internally/system.
3. Run core tests and fresh build. Mount DMG, copy app into a fresh path with spaces, launch with fresh HOME/data and sanitized PATH/PYTHONPATH/source/model configuration. Test native drawing/edit/import, RDKit 3D, checked/saved ORCA input, NumPy/SciPy reviewed recipe, CSV fit/plot, results parsing, file integrity/reopen, menus and graceful missing engine states. Verify archive hashes/signatures/architecture and report exact limitations.
