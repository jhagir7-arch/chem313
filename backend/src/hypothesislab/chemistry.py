"""Deterministic RDKit operations; explicit format-fidelity limitations."""
from __future__ import annotations
import hashlib
import re
try:
    from rdkit import Chem, rdBase
    from rdkit.Chem import Descriptors, rdMolDescriptors, rdDepictor
    from rdkit.Chem.Draw import rdMolDraw2D
    HAS_RDKIT = True
    RDKIT_VERSION = rdBase.rdkitVersion
except ImportError:  # Capability reporting must not fabricate molecular results.
    Chem = rdBase = Descriptors = rdMolDescriptors = rdDepictor = rdMolDraw2D = None
    HAS_RDKIT = False
    RDKIT_VERSION = "NOT_INSTALLED"
from .validation import InputError


def _require_rdkit() -> None:
    if not HAS_RDKIT:
        raise InputError("RDKit is required for molecular graph operations but is not installed in this Python runtime")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def from_smiles(smiles: str):
    _require_rdkit()
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise InputError("RDKit rejected input SMILES")
    return mol


def mol_record_info(molfile: str) -> dict:
    """Reject source forms that RDKit would silently parse only in part."""
    if not isinstance(molfile, str):
        raise InputError("MOL source must be text")
    stripped = molfile.lstrip()
    if (
        stripped.startswith("$RXN")
        or "M  V30 BEGIN RXN" in molfile
        or (stripped.startswith("{") and ("\"rxnArrow\"" in molfile or "\"arrows\"" in molfile or "\"root\"" in molfile))
    ):
        raise InputError(
            "Reaction diagrams ($RXN / KET reaction arrows) are not single-molecule MOL records; "
            "preserve immutable KET original and use reaction-specific workflows (E-015)"
        )
    end_markers = list(re.finditer(r"(?m)^M  END[ \t]*\r?$", molfile))
    if len(end_markers) != 1:
        raise InputError("Exactly one MOL M  END record is required; multi-record input rejected")
    delimiters = list(re.finditer(r"(?m)^\$\$\$\$[ \t]*\r?$", molfile))
    if len(delimiters) > 1:
        raise InputError("Multi-record SDF input rejected; use a separate SDF importer")
    if delimiters and molfile[delimiters[0].end():].strip():
        raise InputError("SDF content after first record delimiter is unsupported")
    tags = re.findall(r"(?m)^>[ \t]*<([^>\r\n]+)>[ \t]*(?:\([^\r\n]*\))?[ \t]*\r?$", molfile)
    trailing = molfile[end_markers[0].end():].strip()
    if trailing and not (trailing.startswith(">") or trailing.startswith("$$$$")):
        raise InputError("Unrecognized content after MOL terminator would be silently ignored")
    if trailing.startswith(">") and not tags:
        raise InputError("Malformed SDF property tag after MOL record")
    return {"input_format": "SDF_SINGLE_RECORD" if (delimiters or tags) else "MOL_SINGLE_RECORD",
            "record_count": 1, "source_property_tags": tags}


def from_molfile(molfile: str):
    _require_rdkit()
    mol_record_info(molfile)
    # Chem.MolFromMolBlock reads one MOL record, not general SDF multi-record data.
    mol = Chem.MolFromMolBlock(molfile, sanitize=True, removeHs=False, strictParsing=True)
    if mol is None:
        raise InputError("RDKit rejected input MOL block; multi-record SDF is not supported")
    if mol.GetNumAtoms() > 1000:
        raise InputError("Molecule exceeds 1000-atom initial cap")
    return mol


def summary(mol) -> dict:
    _require_rdkit()
    return {
        "rdkit_version": rdBase.rdkitVersion,
        "formula": rdMolDescriptors.CalcMolFormula(mol),
        "molecular_weight_g_mol": round(float(Descriptors.MolWt(mol)), 5),
        "isomeric_smiles": Chem.MolToSmiles(mol, isomericSmiles=True),
        "atom_count": mol.GetNumAtoms(),
        "bond_count": mol.GetNumBonds(),
        "formal_charge": sum(a.GetFormalCharge() for a in mol.GetAtoms()),
        "isotope_atoms": [{"index": a.GetIdx(), "mass_number": a.GetIsotope()} for a in mol.GetAtoms() if a.GetIsotope()],
        "chiral_centers": [[idx, label] for idx, label in Chem.FindMolChiralCenters(mol, includeUnassigned=True)],
    }


def svg_for(mol) -> str:
    _require_rdkit()
    clone = Chem.Mol(mol)
    rdDepictor.Compute2DCoords(clone)
    drawer = rdMolDraw2D.MolDraw2DSVG(560, 360)
    drawer.DrawMolecule(clone)
    drawer.FinishDrawing()
    return drawer.GetDrawingText()


def fidelity(molfile: str) -> dict:
    _require_rdkit()
    original = from_molfile(molfile)
    normalized = Chem.MolToMolBlock(original, forceV3000=True)
    reread = from_molfile(normalized)
    before, after = summary(original), summary(reread)
    info = mol_record_info(molfile)
    compared_fields = ["formula", "isomeric_smiles", "atom_count", "bond_count", "formal_charge", "isotope_atoms", "chiral_centers"]
    field_checks = {field: before[field] == after[field] for field in compared_fields}
    field_checks["atom_map_numbers"] = ([a.GetAtomMapNum() for a in original.GetAtoms()]
                                       == [a.GetAtomMapNum() for a in reread.GetAtoms()])
    def coordinate_match():
        if original.GetNumConformers() != reread.GetNumConformers():
            return False
        if not original.GetNumConformers():
            return True
        left, right = original.GetConformer().GetPositions(), reread.GetConformer().GetPositions()
        return bool((abs(left - right) <= 0.0002).all())
    field_checks["coordinates_within_0_0002_angstrom"] = coordinate_match()
    sdf_property_tags = info["source_property_tags"]
    source_metadata_loss = bool(sdf_property_tags or info["input_format"] == "SDF_SINGLE_RECORD")
    warnings = []
    if source_metadata_loss:
        warnings.append("Source SDF properties/record framing are not present in normalized MOL; original source bytes are preserved separately")
    if not all(field_checks.values()):
        warnings.append("Chemical fields changed on RDKit MOL V3000 round trip; investigate before interoperating with other hosts")
    return {
        "original_sha256": digest(molfile.encode("utf-8")),
        "normalized_sha256": digest(normalized.encode("utf-8")),
        "checks": field_checks,
        "all_compared_fields_preserved": all(field_checks.values()),
        "known_fields_passed_without_detected_metadata_loss": bool(all(field_checks.values()) and not source_metadata_loss),
        "unrecognized_source_properties_verified": False,
        "source_metadata_lost_in_derivative": source_metadata_loss,
        "source_input_format": info["input_format"],
        "source_record_count": info["record_count"],
        "normalized_output_format": "MOL_V3000_SINGLE_RECORD",
        "reported_property_tags": sdf_property_tags,
        "warnings": warnings,
        "scope": "RDKit MOL -> RDKit V3000 MOL ONLY; not a Ketcher/Avogadro real-host compatibility certification",
        "normalized_molfile": normalized,
        "summary": before,
    }
