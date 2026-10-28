> Historical design record, not current functionality or a release instruction. See COMMUNITY_HANDOFF.md for present status.

# OpenChem desktop interface refinement

User intent: the existing UI still resembles an AI SaaS dashboard. Keep a mostly black-and-white academic interface and make the actual compiled application easier to use.

Direction: treat the molecule as the working document. Use compact horizontal workspace tabs, a project toolbar, and a single Properties/Qwen inspector. Remove the navigation rail, numbered journey banner and repeated introductory copy. Qwen is optional and retains its draft while hidden. Keep chemical atom colors because they convey molecular meaning.

Implementation:
- Horizontal workspace tabs and matching native Command-1–9 routes; scroll the active tab into view at narrower sizes.
- Dominant molecular canvas with Generate 3D and Save structure in its action toolbar.
- Aligned property rows, geometry status and an optional Qwen inspector; applying a proposal returns to the structure properties.
- Fixed application chrome and status bar, with scrolling inside the workspace. Below 1040 pixels the inspector sits beneath the editor. Fit structure changes the viewport and preserves exact MOL coordinates.
- Optional, collapsed input suggestion in scientific tools; compact consistent typography for methods, values and source.
- Derive geometry freshness from the observed drawing and conformer source; delayed editor notifications must not mark a newly generated geometry stale.
- Preserve project/editor guards, reviewed writes, running job state, native menus, engine boundaries and artifacts.

Verification: frontend type/build checks and existing parser/recipe tests; real local workflow through geometry, PySCF, reviewed recipes and saved ORCA input; desktop layouts at 1440, 1280 and 850 pixels; frozen AppKit/WKWebView workflow including Qwen and Avogadro. Save screenshots and evidence for this UI revision separately from the earlier release receipts.

Packaging: OpenChem 0.8.0 build 10. Preserve the previous installed build in the local installation backup folder. Earlier DMG and framework ZIP remain their original snapshots.
