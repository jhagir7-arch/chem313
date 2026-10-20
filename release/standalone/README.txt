Chem313 1.0.0-preview.5 — standalone Apple Silicon Mac research preview

Drag Chem313.app to Applications. Python, Node, Homebrew and terminal setup
are not prerequisites for this standalone app. Apple Silicon, macOS 14+.
The embedded binary deployment-target audit passes at 14.0; runtime testing
here uses macOS 27. Older OS releases and Intel Macs are not verified.

The app is ad-hoc signed, not Apple Developer ID signed or notarized. macOS
may block an Internet download. Only use Privacy & Security > Open Anyway
for a copy whose provenance and checksum you trust.

Start in Molecule with water, methane or ethanol. Inspect the formula,
build a starting structure and compare shapes. Bars show relative MMFF/UFF
force-field energies for the same molecule and model, not quantum results.
Use the Q-Chem lesson to review atoms, coordinates, fixed-geometry settings,
a coordinate-derived identity check and the exact input before downloading.

Included: Ketcher/Indigo, RDKit, 3Dmol, embedded Python, NumPy, SciPy and
Matplotlib, project records and reviewed JSON research operations. Four core
workspaces are visible by default; experimental integrations are under Labs.
The Guide includes a searchable feature directory with scope and evidence.

ORCA and Q-Chem require separately licensed installations. Neither is bundled
or configured by this package. No real licensed quantum run has yet been
verified on the maintainer's machine. Avogadro, Open Babel, PySCF, tblite and
Qwen weights/adapters are not bundled. No model downloads on launch.

Formerly OpenChem. Existing data remains in ~/Library/Application Support/
OpenChem for compatibility. Quit the app before backing up that folder.
This research preview does not establish general scientific accuracy.

Source and feedback: https://github.com/jhagir7-arch/openchem
Use GitHub Issues; keep private research files and credentials out of reports.
App code: Apache-2.0. Dependencies retain their own terms. Notices and the
native payload checksum manifest are in Contents/Resources/licenses/standalone-core.
