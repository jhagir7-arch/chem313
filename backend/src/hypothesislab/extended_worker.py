"""Isolated worker for exercised extended engines; accepts bounded JSON only."""
from __future__ import annotations

import contextlib
import hashlib
import importlib.metadata as metadata
import json
import os
import resource
import sys
import time

# Set native-library thread limits before importing any scientific module. The
# worker reports one thread and is designed for bounded single-request use.
for _thread_limit in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_thread_limit] = "1"

from .extended_contracts import OPERATIONS, validate_operation


BOHR_PER_ANGSTROM = 1.8897261254578281


def run(op: str, p: dict) -> dict:
    if op == "pyscf.rhf_singlepoint":
        from pyscf import gto, scf
        from pyscf.data.elements import ELEMENTS

        atom = [(ELEMENTS[z], xyz) for z, xyz in zip(p["atomic_numbers"], p["coordinates_angstrom"])]
        molecule = gto.M(atom=atom, unit="Angstrom", basis=p["basis"], charge=p["charge"], spin=0, verbose=0)
        calculation = scf.RHF(molecule)
        calculation.max_cycle = 50
        energy = calculation.kernel()
        if not calculation.converged:
            raise ValueError("PySCF RHF did not converge within 50 SCF cycles")
        return {
            "energy_hartree": float(energy),
            "converged": True,
            "electrons": molecule.nelectron,
            "basis": p["basis"],
            "charge": p["charge"],
            "atoms": molecule.natm,
            "method": "RHF",
        }
    if op == "tblite.gfn2_singlepoint":
        import numpy as np
        from tblite.interface import Calculator

        positions = np.asarray(p["coordinates_angstrom"], dtype=float) * BOHR_PER_ANGSTROM
        calculator = Calculator("GFN2-xTB", np.asarray(p["atomic_numbers"], dtype=int), positions, charge=p["charge"])
        calculator.set("verbosity", 0)
        result = calculator.singlepoint()
        return {
            "energy_hartree": float(result.get("energy")),
            "partial_charges_e": [float(x) for x in result.get("charges")],
            "charge": p["charge"],
            "atoms": len(p["atomic_numbers"]),
            "method": "GFN2-xTB",
        }
    if op == "matchms.cosine_greedy":
        import numpy as np
        from matchms import Spectrum
        from matchms.similarity import CosineGreedy

        reference = Spectrum(
            mz=np.asarray(p["reference_mz"], dtype=float),
            intensities=np.asarray(p["reference_intensities"], dtype=float),
            metadata={"precursor_mz": 0.0},
        )
        query = Spectrum(
            mz=np.asarray(p["query_mz"], dtype=float),
            intensities=np.asarray(p["query_intensities"], dtype=float),
            metadata={"precursor_mz": 0.0},
        )
        score_record = CosineGreedy(tolerance=p["tolerance_da"]).pair(reference, query)
        return {
            "cosine_score": float(score_record["score"]),
            "matched_peak_pairs": int(score_record["matches"]),
            "tolerance_da": p["tolerance_da"],
            "reference_peak_count": len(p["reference_mz"]),
            "query_peak_count": len(p["query_mz"]),
            "method": "CosineGreedy",
        }
    if op == "meeko.prepare_pdbqt":
        from meeko import MoleculePreparation, PDBQTWriterLegacy
        from rdkit import Chem
        from rdkit.Chem import AllChem, Lipinski

        molecule = Chem.MolFromSmiles(p["smiles"])
        if molecule is None:
            raise ValueError("SMILES could not be parsed by RDKit")
        molecule = Chem.AddHs(molecule)
        if AllChem.EmbedMolecule(molecule, randomSeed=42, maxAttempts=20) != 0:
            raise ValueError("RDKit ETKDG embedding failed")
        if AllChem.UFFOptimizeMolecule(molecule, maxIters=100) != 0:
            raise ValueError("RDKit UFF did not converge within 100 iterations")
        setup = list(MoleculePreparation().prepare(molecule))[0]
        pdbqt, is_ok, error = PDBQTWriterLegacy.write_string(setup)
        if not is_ok:
            raise ValueError(f"Meeko PDBQT writing failed: {error}")
        return {
            "pdbqt": pdbqt,
            "pdbqt_sha256": hashlib.sha256(pdbqt.encode("utf-8")).hexdigest(),
            "pdbqt_atom_records": sum(line.startswith(("ATOM", "HETATM")) for line in pdbqt.splitlines()),
            "atoms": setup.get_num_mol_atoms(),
            "rotatable_bonds": int(Lipinski.NumRotatableBonds(molecule)),
            "method": "Meeko MoleculePreparation / PDBQTWriterLegacy",
        }
    raise ValueError("Unimplemented operation")


def main() -> None:
    start = time.monotonic()
    resource.setrlimit(resource.RLIMIT_CPU, (110, 115))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1_500_000, 1_500_000))
    try:
        raw = sys.stdin.buffer.read(250_001)
        if len(raw) > 250_000:
            raise ValueError("Input exceeds 250 KB")
        request = json.loads(raw)
        if not isinstance(request, dict) or set(request) != {"operation", "inputs"}:
            raise ValueError("Request must contain only operation and inputs")
        op = request["operation"]
        inputs = validate_operation(op, request["inputs"])
        with contextlib.redirect_stdout(sys.stderr):
            output = run(op, inputs)
        engine = OPERATIONS[op][0]
        result = {
            "schema": "openchem.science.result.v1",
            "operation": op,
            "engine": engine,
            "version": metadata.version({"PySCF": "pyscf", "tblite": "tblite", "matchms": "matchms", "Meeko": "meeko"}[engine]),
            "output": output,
            "units": OPERATIONS[op][3],
            "limitations": OPERATIONS[op][4],
            "resources": {
                "wall_seconds": time.monotonic() - start,
                "user_cpu_seconds": resource.getrusage(resource.RUSAGE_SELF).ru_utime,
                "max_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "gpu": False,
                "threads": 1,
            },
        }
        encoded = json.dumps(result, allow_nan=False)
        if len(encoded.encode()) > 1_000_000:
            raise ValueError("Result exceeds 1 MB cap")
        print(encoded)
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"}))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
