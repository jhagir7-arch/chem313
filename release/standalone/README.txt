Chem313 1.0.0-preview.6 — standalone Apple Silicon Mac research preview

Drag Chem313.app to Applications. Python, Node, Homebrew and terminal setup
are not prerequisites for this standalone app. Apple Silicon, macOS 14+.
The embedded binary deployment-target audit passes at 14.0; runtime testing
here uses macOS 27. Older OS releases and Intel Macs are not verified.

The app is ad-hoc signed, not Apple Developer ID signed or notarized. macOS
may block an Internet download. Only use Privacy & Security > Open Anyway
for a copy whose provenance and checksum you trust.

Start in Calculate > First calculation. Choose ethanol and click Run shape
calculation. See its relaxed 3D shape, before/after MMFF94 energies, convergence,
and a saved project report. Download record exports parameters, model version,
values and file hashes. Water and methane are also included. No code, engine
account, AI model or internet connection is needed for this lesson.
This is a real molecular mechanics calculation, not a quantum calculation or
a prediction of a reaction. Compare energies only within the same molecule,
model and run. The ORCA option remains available for licensed installations.

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
