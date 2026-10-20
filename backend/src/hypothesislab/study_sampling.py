"""Bounded, reproducible force-field conformer sampling for molecule studies.

This reports generated conformers and their force-field energies.  It does not
establish a global minimum, free energy, or experimental molecular structure.
"""
from __future__ import annotations

import math
import time
from typing import Any, Callable

from rdkit import Chem, rdBase
from rdkit.Chem import Lipinski, rdMolAlign, rdMolDescriptors

from .conformers import molecule_conformer


SEEDS = (42, 137, 271, 811, 1297, 1879, 2081, 3557)
_SUPPORTED_ELEMENTS = frozenset({"H", "B", "C", "N", "O", "F", "Si", "P", "S", "Cl"})
_RMSD_THRESHOLD_ANGSTROM = 0.25
_MAX_SCHEDULING_SECONDS = 60.0


def _validate_molecule(smiles: str):
    if not isinstance(smiles, str) or not smiles.strip():
        raise ValueError("'smiles' must be a non-empty string.")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError("RDKit could not parse the supplied SMILES.")
    if len(Chem.GetMolFrags(mol)) != 1:
        raise ValueError("Study sampling supports one connected molecule only.")
    if Chem.GetFormalCharge(mol) != 0:
        raise ValueError("Study sampling supports neutral molecules only.")
    if sum(atom.GetNumRadicalElectrons() for atom in mol.GetAtoms()):
        raise ValueError("Study sampling supports closed-shell molecules only.")
    if any(atom.GetIsotope() for atom in mol.GetAtoms()):
        raise ValueError("Study sampling does not support isotopically labelled molecules.")
    unsupported = sorted({atom.GetSymbol() for atom in mol.GetAtoms()} - _SUPPORTED_ELEMENTS)
    if unsupported:
        raise ValueError("Unsupported element(s): " + ", ".join(unsupported))
    heavy_atoms = mol.GetNumHeavyAtoms()
    if not 1 <= heavy_atoms <= 40:
        raise ValueError("Study sampling supports from 1 through 40 heavy atoms.")
    if Lipinski.NumRotatableBonds(mol) > 12:
        raise ValueError("Study sampling supports at most 12 rotatable bonds.")
    return mol


def _require_count(count: int) -> int:
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= len(SEEDS):
        raise ValueError("'count' must be an integer from 1 through 8.")
    return count


def _heavy_atom_geometry(sdf: str):
    """Return a fresh heavy-atom molecule so alignment cannot alter saved SDF."""
    mol = Chem.MolFromMolBlock(sdf.split("$$$$", 1)[0], removeHs=False)
    if mol is None or not mol.GetNumConformers():
        raise ValueError("Generated conformer did not contain readable 3D coordinates.")
    return Chem.RemoveHs(Chem.Mol(mol))


def _best_heavy_atom_rmsd(candidate, representative) -> float:
    # GetBestRMS aligns the probe; copies make that operation non-mutating for
    # the representative geometry retained with the output candidate.
    return float(rdMolAlign.GetBestRMS(Chem.Mol(candidate), Chem.Mol(representative)))


def _candidate_from_result(seed: int, result: dict[str, Any]) -> dict[str, Any]:
    candidate = dict(result)
    candidate["seed"] = seed
    energy = candidate.get("energy")
    if not isinstance(energy, (int, float)) or isinstance(energy, bool) or not math.isfinite(float(energy)):
        candidate.update(status="failed", error="Conformer generation returned a non-finite energy.")
        return candidate
    candidate["energy"] = float(energy)
    if not candidate.get("converged", False):
        candidate["status"] = "not_converged"
    else:
        candidate["status"] = "unique"
    return candidate


def _add_relative_energies(candidates: list[dict[str, Any]]) -> None:
    unique = [row for row in candidates if row.get("status") == "unique"]
    signatures = {(row.get("force_field"), row.get("energy_unit")) for row in unique}
    if not unique or len(signatures) != 1:
        return
    minimum = min(row["energy"] for row in unique)
    for row in unique:
        row["relative_energy"] = float(row["energy"] - minimum)


def sample_shapes(
    smiles: str,
    count: int = 5,
    stop_requested: Callable[[], bool] = lambda: False,
    on_progress: Callable[[int, int], None] = lambda completed, total: None,
) -> dict[str, Any]:
    """Generate up to eight seeded conformers and deduplicate their shapes.

    Cancellation and the 60-second scheduling bound are checked between whole
    conformer runs, preserving every candidate that has already finished.
    """
    mol = _validate_molecule(smiles)
    count = _require_count(count)
    if not callable(stop_requested) or not callable(on_progress):
        raise ValueError("'stop_requested' and 'on_progress' must be callable.")

    started = time.monotonic()
    candidates: list[dict[str, Any]] = []
    representatives: list[tuple[int, Any]] = []
    cancelled = False
    for seed in SEEDS[:count]:
        if stop_requested() or time.monotonic() - started >= _MAX_SCHEDULING_SECONDS:
            cancelled = True
            break
        try:
            candidate = _candidate_from_result(seed, molecule_conformer({"smiles": smiles, "seed": seed}))
            if candidate["status"] != "not_converged" and candidate["status"] != "failed":
                geometry = _heavy_atom_geometry(candidate["sdf"])
                for representative_seed, representative in representatives:
                    rmsd = _best_heavy_atom_rmsd(geometry, representative)
                    if rmsd <= _RMSD_THRESHOLD_ANGSTROM:
                        candidate.update(status="duplicate", duplicate_of=representative_seed, rmsd=rmsd)
                        break
                else:
                    candidate["status"] = "unique"
                    representatives.append((seed, geometry))
        except Exception as exc:  # A single seed must not discard the study's partial evidence.
            candidate = {"seed": seed, "status": "failed", "energy": None, "error": str(exc)}
        candidates.append(candidate)
        on_progress(len(candidates), count)

    _add_relative_energies(candidates)
    unique_count = sum(row.get("status") == "unique" for row in candidates)
    return {
        "canonical_smiles": Chem.MolToSmiles(mol, isomericSmiles=True),
        "formula": rdMolDescriptors.CalcMolFormula(mol),
        "rdkit_version": rdBase.rdkitVersion,
        "requested": count,
        "completed": len(candidates),
        "cancelled": cancelled,
        "candidates": candidates,
        "unique_count": unique_count,
        "scope": (
            "Seeded RDKit force-field conformer sampling with heavy-atom RMSD deduplication; "
            "generated structures and force-field energies are not free energies or global-minimum claims."
        ),
        "summary": f"Completed {len(candidates)} of {count} requested seeded conformer candidates; {unique_count} unique converged shapes.",
    }
