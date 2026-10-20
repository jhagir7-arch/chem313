"""Validated, bounded ORCA input rendering for locally prepared molecules.

This module prepares an input file only.  It never invokes ORCA or treats a
force-field geometry as a quantum-chemical result.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any

from .chemistry import from_molfile, mol_record_info
from .identity import identity_check, mol_inchi
from .validation import InputError


METHOD_BASIS = {
    "HF": {"def2-SVP"},
    "B3LYP": {"def2-SVP"},
    "PBE0": {"def2-SVP"},
    "r2SCAN-3c": {"built-in"},
}
JOB_KEYWORDS = {
    "single_point": "SP",
    "optimization": "Opt",
    "optimization_frequency": "Opt Freq",
}
# This first preparation slice is for common main-group molecular inputs.
# ECP, relativistic, transition-metal and custom basis selection need a
# separately reviewed contract rather than an apparently general-purpose form.
SUPPORTED_ATOMIC_NUMBERS = frozenset({1, 5, 6, 7, 8, 9, 14, 15, 16, 17})
MAX_GEOMETRY_BYTES = 250_000


def _require_exact_keys(params: dict[str, Any]) -> None:
    expected = {"geometry_sdf", "job_type", "charge", "multiplicity", "method", "basis"}
    if not isinstance(params, dict) or set(params) != expected:
        raise InputError("ORCA preparation requires exactly geometry, job type, charge, multiplicity, method and basis")


def prepare_orca_input(params: dict[str, Any]) -> dict[str, Any]:
    """Validate a single 3D SDF record and return an in-memory input preview."""
    _require_exact_keys(params)
    geometry_sdf = params["geometry_sdf"]
    if not isinstance(geometry_sdf, str) or not geometry_sdf.strip():
        raise InputError("A non-empty generated 3D geometry is required")
    if len(geometry_sdf.encode("utf-8")) > MAX_GEOMETRY_BYTES:
        raise InputError("Geometry exceeds the 250 KB preparation limit")
    if not all(isinstance(params[key], str) for key in ("job_type", "method", "basis")):
        raise InputError("Job type, method and basis must be selected text values")
    job_type, method, basis = params["job_type"], params["method"], params["basis"]
    if job_type not in JOB_KEYWORDS:
        raise InputError("Choose a supported calculation type")
    if method not in METHOD_BASIS or basis not in METHOD_BASIS[method]:
        raise InputError("Choose one supported method and basis pairing")
    charge, multiplicity = params["charge"], params["multiplicity"]
    if isinstance(charge, bool) or not isinstance(charge, int) or not -10 <= charge <= 10:
        raise InputError("Charge must be a whole number from -10 through 10")
    if isinstance(multiplicity, bool) or not isinstance(multiplicity, int) or not 1 <= multiplicity <= 9:
        raise InputError("Multiplicity must be a whole number from 1 through 9")

    record = mol_record_info(geometry_sdf)
    # The original record, including any SDF fields, is retained as supplied.
    # Only the atom/coordinate block is rendered to ORCA.
    if record["record_count"] != 1:
        raise InputError("Exactly one SDF geometry record is required")
    mol = from_molfile(geometry_sdf)
    if not mol.GetNumConformers() or not mol.GetConformer().Is3D():
        raise InputError("Generate a 3D starting geometry before preparing ORCA input")
    if any(atom.GetNumImplicitHs() for atom in mol.GetAtoms()):
        raise InputError("The starting geometry has implicit hydrogens; generate a complete explicit-hydrogen 3D conformer before preparing ORCA input")
    if any(atom.GetAtomicNum() not in SUPPORTED_ATOMIC_NUMBERS for atom in mol.GetAtoms()):
        raise InputError("This ORCA preparation workflow supports H, B, C, N, O, F, Si, P, S and Cl; other elements need a separately reviewed basis and electronic-state setup")
    if any(atom.GetIsotope() for atom in mol.GetAtoms()):
        raise InputError("Isotope masses are unsupported in this first ORCA preparation workflow; preserve the source and use an isotope-aware setup")
    conformer = mol.GetConformer()
    coordinates: list[tuple[str, float, float, float]] = []
    for atom in mol.GetAtoms():
        point = conformer.GetAtomPosition(atom.GetIdx())
        xyz = (float(point.x), float(point.y), float(point.z))
        if not all(math.isfinite(value) for value in xyz):
            raise InputError("The 3D geometry contains non-finite coordinates")
        coordinates.append((atom.GetSymbol(), *xyz))
    electrons = sum(atom.GetAtomicNum() for atom in mol.GetAtoms()) - charge
    if electrons <= 0 or multiplicity > electrons + 1 or (electrons + multiplicity) % 2 != 1:
        raise InputError("Charge and multiplicity are incompatible with this molecular electron count")
    formal_charge = sum(atom.GetFormalCharge() for atom in mol.GetAtoms())
    identity = identity_check(coordinates, expected_inchi=mol_inchi(mol), charge=formal_charge)
    if identity["status"] == "mismatch":
        raise InputError(identity["detail"])

    keywords = [method]
    if basis != "built-in":
        keywords.append(basis)
    keywords.extend(JOB_KEYWORDS[job_type].split())
    lines = ["! " + " ".join(keywords), "", f"* xyz {charge} {multiplicity}"]
    lines.extend(f"{symbol:<2} {x: .10f} {y: .10f} {z: .10f}" for symbol, x, y, z in coordinates)
    lines.extend(["*", ""])
    rendered = "\n".join(lines)
    geometry_bytes = geometry_sdf.encode("utf-8")
    warnings = []
    if identity["status"] == "inconclusive":
        warnings.append("Identity check inconclusive: " + identity["detail"])
    if formal_charge != charge:
        warnings.append("Requested charge differs from the drawn structure's formal charge; review the intended protonation and electronic state.")
    if multiplicity != 1:
        warnings.append("Open-shell input: confirm multiplicity and method suitability before running ORCA.")
    return {
        "input_text": rendered,
        "geometry_sha256": hashlib.sha256(geometry_bytes).hexdigest(),
        "input_sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
        "atom_count": mol.GetNumAtoms(),
        "coordinate_units": "angstrom",
        "coordinate_checks": {"has_3d_conformer": True, "all_coordinates_finite": True, "all_hydrogens_explicit": True, "common_main_group_scope": True, "charge_spin_consistent": True, "inchi_round_trip": identity["status"] == "match"},
        "identity_check": identity,
        "electron_count": electrons,
        "settings": {"job_type": job_type, "charge": charge, "multiplicity": multiplicity, "method": method, "basis": basis},
        "source_input_format": record["input_format"],
        "source_property_tags": record["source_property_tags"],
        "warnings": warnings,
        "scope": "Prepared ORCA input from a locally generated 3D starting geometry. It does not run ORCA, verify force-field convergence, or establish chemical validity.",
    }
