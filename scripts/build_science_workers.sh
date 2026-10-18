#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Locked, separate CPU environments. No model weights, GPU runtimes or remote jobs.
.engines/science/bin/python -m PyInstaller --noconfirm --clean --name science-worker \
  --paths backend/src --distpath build/workers --workpath build/pyinstaller-science --specpath build \
  --collect-data cantera --collect-data openmm --collect-data pymatgen.core \
  --collect-data MDAnalysis --collect-submodules MDAnalysis.lib.formats --collect-data spglib --collect-data nmrglue \
  --collect-submodules cantera --collect-data rocrate \
  --copy-metadata numpy --copy-metadata scipy --copy-metadata gemmi --copy-metadata spglib \
  --copy-metadata pymatgen --copy-metadata pymatgen-core --copy-metadata pint --copy-metadata pandas \
  --copy-metadata polars --copy-metadata lmfit --copy-metadata nmrglue --copy-metadata pyteomics \
  --copy-metadata biopython --copy-metadata optuna --copy-metadata cantera --copy-metadata openmm \
  --copy-metadata mdtraj --copy-metadata MDAnalysis --copy-metadata rocrate --copy-metadata ord-schema \
  --exclude-module tkinter --exclude-module pytest --exclude-module IPython \
  --exclude-module torch --exclude-module jax --exclude-module tensorflow --exclude-module PyQt5 \
  --exclude-module PySide6 desktop/science_service.py

.engines/extended/bin/python -m PyInstaller --noconfirm --clean --name extended-worker \
  --paths backend/src --distpath build/workers --workpath build/pyinstaller-extended --specpath build \
  --collect-data pyscf --collect-binaries pyscf --collect-all tblite \
  --collect-data matchms --collect-data meeko --collect-data rdkit --collect-binaries rdkit \
  --copy-metadata pyscf --copy-metadata tblite --copy-metadata matchms --copy-metadata meeko --copy-metadata rdkit \
  --exclude-module tkinter --exclude-module pytest --exclude-module IPython \
  --exclude-module torch --exclude-module jax --exclude-module tensorflow --exclude-module PyQt5 \
  --exclude-module PySide6 --exclude-module pysb --exclude-module bionetgen desktop/extended_service.py
