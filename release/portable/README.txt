Chem313 portable core — native Windows, Linux, or macOS build

This folder is produced by a native build on its target operating system. Open
Chem313 (Chem313.exe on Windows). It starts a local loopback-only service and
opens the browser only after that service reports readiness. Recipients need no
separate Python, Node.js, or package manager.

First calculation

1. Extract the whole download, keeping Chem313 beside its _internal folder.
2. Open Chem313.exe on Windows, or run ./Chem313 on Linux.
3. In the browser, open Calculate > First calculation, choose Ethanol, and
   click Run shape calculation. Water and methane are also available.
4. Read the final 3D shape and before/after MMFF94 energy chart in kcal/mol.
5. Click Download record to keep the parameters, model version and file hashes.

This is a real included molecular-mechanics calculation. It relaxes one
molecule's shape; it does not establish a reaction or a quantum result.
Windows requires Windows 10+ (or Windows Server 2022+), x64. The Windows
UCRT/API-set libraries come from the operating system, not this archive.
Linux requires x86_64 with glibc 2.35+; the native candidate is tested on
Ubuntu 22.04. Other distributions and ARM builds are not yet verified.

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

Windows runtime terms

The Windows build includes Microsoft Distributable Code supplied with CPython.
Before its first launch, Chem313 opens the retained terms at
licenses/portable-core/windows-cpython-runtime/CPYTHON-3.13.16-CRTLICENSE.txt
and requires an explicit Yes click. The acceptance record is tied to that
file's SHA-256; a changed terms file is shown and accepted again. This is a
condition of using the Windows portable build.
