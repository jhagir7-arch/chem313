"""Coordinate-only identity check for prepared calculation inputs.

Bonds are re-perceived from the element symbols and Cartesian coordinates
exactly as written to an engine input, and the standard InChI of that perceived
structure is compared with the source structure's InChI.  A match shows the
exported coordinates still encode the intended connectivity, hydrogen count and
3D-perceivable stereochemistry.  It does not show that the geometry is a
minimum or that the chosen method suits the molecule.
"""
from __future__ import annotations

from typing import Any, Sequence

from rdkit import Chem
from rdkit.Chem import rdDetermineBonds
from rdkit.rdBase import BlockLogs

MAX_IDENTITY_ATOMS = 200
METHOD = "RDKit DetermineBonds (covalent radii, bond orders) from exported coordinates; standard InChI comparison"
SCOPE = ("Confirms the exported coordinates reproduce the source structure's standard InChI. "
         "It does not validate the geometry, electronic state or method choice.")

Coordinate = tuple[str, float, float, float]


def mol_inchi(mol: Chem.Mol) -> str | None:
    blocker = BlockLogs()
    try:
        value = Chem.MolToInchi(mol)
    except Exception:
        value = None
    finally:
        del blocker
    return value or None


def coordinate_inchi(coordinates: Sequence[Coordinate], charge: int) -> str | None:
    xyz = f"{len(coordinates)}\n\n" + "\n".join(f"{s} {x:.10f} {y:.10f} {z:.10f}" for s, x, y, z in coordinates)
    blocker = BlockLogs()
    try:
        mol = Chem.MolFromXYZBlock(xyz)
        if mol is None:
            return None
        rdDetermineBonds.DetermineBonds(mol, charge=charge)
        Chem.AssignStereochemistryFrom3D(mol)
    except Exception:
        return None
    finally:
        del blocker
    return mol_inchi(mol)


def _key(inchi: str | None) -> str | None:
    return Chem.InchiToInchiKey(inchi) if inchi else None


def identity_check(coordinates: Sequence[Coordinate], *, expected_inchi: str | None, charge: int) -> dict[str, Any]:
    """Return match, mismatch or inconclusive with both identifiers and a plain-language detail."""
    result: dict[str, Any] = {"method": METHOD, "scope": SCOPE, "expected_inchi": expected_inchi,
                              "expected_inchikey": _key(expected_inchi), "observed_inchi": None, "observed_inchikey": None}
    if expected_inchi is None:
        return {**result, "status": "inconclusive", "detail": "An InChI could not be generated for the source structure."}
    if len(coordinates) > MAX_IDENTITY_ATOMS:
        return {**result, "status": "inconclusive",
                "detail": f"Identity check is limited to {MAX_IDENTITY_ATOMS} atoms; review larger structures manually."}
    observed = coordinate_inchi(coordinates, charge)
    result.update(observed_inchi=observed, observed_inchikey=_key(observed))
    if observed is None:
        return {**result, "status": "inconclusive",
                "detail": "Bonds could not be perceived from the exported coordinates; check for overlapping or distant atoms."}
    if observed == expected_inchi:
        return {**result, "status": "match", "detail": "The exported coordinates reproduce the source structure."}
    if result["observed_inchikey"][:14] != result["expected_inchikey"][:14]:
        detail = ("The exported coordinates describe a different molecule than the source structure: atoms are too close, "
                  "too far apart or connected differently. Regenerate the 3D geometry before exporting.")
    else:
        detail = ("The exported coordinates keep the connectivity but not the source stereochemistry. "
                  "Regenerate the 3D geometry or check the drawn stereocentres before exporting.")
    return {**result, "status": "mismatch", "detail": detail}
