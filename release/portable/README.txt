Chem313 portable core — native Windows, Linux, or macOS build

This folder is produced by a native build on its target operating system. Open
Chem313 (Chem313.exe on Windows). It starts a local loopback-only service and
opens the browser only after that service reports readiness. Recipients need no
separate Python, Node.js, or package manager.

Included: the built web interface, RDKit structure inspection and force-field
conformers, NumPy summaries, SciPy calibration fits, Matplotlib SVG plots,
reviewed JSON research recipes, ORCA input preparation/results review, and
local immutable project artifacts.

Data stays in the existing per-user OpenChem locations for compatibility with
earlier records: %LOCALAPPDATA%\OpenChem on Windows, $XDG_DATA_HOME/OpenChem
(or ~/.local/share/OpenChem) on Linux, and ~/Library/Application Support/OpenChem
on macOS. Back up that folder only after quitting Chem313. Keep original
scientific source files.

ORCA is not included; running it requires the recipient's own licensed ORCA
installation. Avogadro, Open Babel, PySCF, tblite, and Qwen/MLX models are not
bundled. No model or dataset downloads on launch.

Each platform must be built and tested natively. A macOS build cannot create a
validated Windows or Linux application. A successful native smoke test only
confirms the tested candidate; it is downloadable only when both
licenses/portable-core/MANIFEST.json and DISTRIBUTION_REVIEW.json pass.

App code is Apache-2.0. See LICENSE, NOTICE, THIRD_PARTY_NOTICES.md, and
licenses/portable-core for retained runtime notices.
