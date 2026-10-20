"""Conformer adapter from the preserved HypothesisLab C02 handoff.
RDKit ETKDG with MMFF/UFF; generated geometry is not an experimental result.
"""
from typing import Any

def _dependency(module: str, feature: str):
    try:
        return __import__(module, fromlist=["*"])
    except ImportError as exc:
        raise RuntimeError(f"Optional dependency '{module}' is required for {feature}.") from exc

def _string(params: dict, key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"'{key}' must be a non-empty string.")
    return value

def molecule_conformer(params: dict) -> dict:
    if not isinstance(params, dict):
        raise ValueError("Parameters must be an object.")
    Chem = _dependency("rdkit.Chem", "conformer generation")
    AllChem = _dependency("rdkit.Chem.AllChem", "conformer generation and minimization")
    smiles = _string(params, "smiles")
    seed = params.get("seed", 42)
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2_147_483_647:
        raise ValueError("'seed' must be an integer from 0 through 2147483647.")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError("RDKit could not parse the supplied SMILES.")
    mol = Chem.AddHs(mol)
    embed = AllChem.ETKDGv3()
    embed.randomSeed = seed
    conf_id = AllChem.EmbedMolecule(mol, embed)
    if conf_id < 0:
        raise ValueError("ETKDG conformer generation failed.")
    if AllChem.MMFFHasAllMoleculeParams(mol):
        force_field, status = "MMFF", AllChem.MMFFOptimizeMolecule(mol, confId=conf_id)
    elif AllChem.UFFHasAllMoleculeParams(mol):
        force_field, status = "UFF", AllChem.UFFOptimizeMolecule(mol, confId=conf_id)
    else:
        raise ValueError("No supported MMFF or UFF parameters exist for this molecule.")
    energy = (AllChem.MMFFGetMoleculeForceField(mol, AllChem.MMFFGetMoleculeProperties(mol), confId=conf_id).CalcEnergy()
              if force_field == "MMFF" else AllChem.UFFGetMoleculeForceField(mol, confId=conf_id).CalcEnergy())
    molblock = Chem.MolToMolBlock(mol, confId=conf_id)
    coordinates = mol.GetConformer(conf_id).GetPositions().tolist()
    return {"seed": seed, "force_field": force_field, "converged": status == 0,
            "convergence_status": int(status), "energy": float(energy), "energy_unit": "kcal/mol",
            "coordinates_status": "generated_3d", "coordinate_units": "angstrom",
            "coordinate_count": len(coordinates), "coordinates": coordinates, "atom_count": len(coordinates),
            "atomic_numbers": [atom.GetAtomicNum() for atom in mol.GetAtoms()],
            "formal_charge": int(Chem.GetFormalCharge(mol)),
            "sdf": molblock + "$$$$\n", "rdkit_version": _dependency("rdkit.rdBase", "version reporting").rdkitVersion}


# Deliberately bounded first lesson: no arbitrary large structures or reaction claims.
FIRST_MOLECULES = {"CCO": "Ethanol", "O": "Water", "C": "Methane"}


def validate_relaxation(params: dict) -> None:
    if not isinstance(params, dict) or set(params) - {"smiles", "seed"}:
        raise ValueError("Choose a supported molecule and optional random seed.")
    if not isinstance(params.get("smiles"), str) or params["smiles"] not in FIRST_MOLECULES:
        raise ValueError("The first calculation supports ethanol, water and methane.")
    seed = params.get("seed", 42)
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2_147_483_647:
        raise ValueError("seed must be an integer from 0 through 2147483647")


def relax_geometry(params: dict) -> dict:
    """Real, reproducible MMFF94 relaxation; energies refer to exact saved geometries."""
    import math
    from .chemistry import summary, svg_for
    validate_relaxation(params)
    Chem = _dependency("rdkit.Chem", "geometry relaxation")
    AllChem = _dependency("rdkit.Chem.AllChem", "MMFF94 relaxation")
    mol = Chem.AddHs(Chem.MolFromSmiles(params["smiles"]))
    embed = AllChem.ETKDGv3()
    embed.randomSeed = params.get("seed", 42)
    if AllChem.EmbedMolecule(mol, embed) < 0:
        raise ValueError("The starting shape could not be generated. Try another molecule.")
    # Round-trip before evaluating so another program can reproduce the exact energy
    # from the exported SDF rather than unavailable full-precision coordinates.
    initial_sdf = Chem.MolToMolBlock(mol) + "$$$$\n"
    mol = Chem.MolFromMolBlock(initial_sdf.split("$$$$")[0], removeHs=False)
    props = AllChem.MMFFGetMoleculeProperties(mol, mmffVariant="MMFF94")
    if props is None:
        raise ValueError("MMFF94 parameters are unavailable for this structure.")
    ff = AllChem.MMFFGetMoleculeForceField(mol, props)
    initial_key = Chem.MolToInchiKey(mol)
    initial = float(ff.CalcEnergy())
    code = int(ff.Minimize(maxIts=1000, forceTol=1e-4, energyTol=1e-6))
    sdf = Chem.MolToMolBlock(mol) + "$$$$\n"
    final_mol = Chem.MolFromMolBlock(sdf.split("$$$$")[0], removeHs=False)
    final = float(AllChem.MMFFGetMoleculeForceField(final_mol, AllChem.MMFFGetMoleculeProperties(final_mol, mmffVariant="MMFF94")).CalcEnergy())
    if not all(math.isfinite(value) for value in (initial, final)):
        raise ValueError("The calculation returned an invalid energy; no result was saved.")
    final_key = Chem.MolToInchiKey(final_mol)
    expected_key = Chem.MolToInchiKey(Chem.MolFromSmiles(params["smiles"]))
    if not expected_key or initial_key != expected_key or final_key != expected_key:
        raise ValueError("The saved structure no longer matches the selected molecule.")
    info = summary(final_mol)
    return {"schema": "chem313.geometry-relaxation.v1", "name": FIRST_MOLECULES[params["smiles"]],
            "smiles": params["smiles"], "canonical_smiles": Chem.MolToSmiles(Chem.RemoveHs(final_mol)),
            "formula": info["formula"], "atom_count": final_mol.GetNumAtoms(), "formal_charge": 0,
            "inchikey": expected_key, "identity_status": "MATCH", "seed": params.get("seed", 42),
            "embedding": "ETKDGv3", "force_field": "MMFF94", "iterations_limit": 1000,
            "force_tolerance": 1e-4, "energy_tolerance": 1e-6,
            "converged": code == 0, "convergence_status": code,
            "initial_energy_kcal_mol": initial, "final_energy_kcal_mol": final,
            "energy_change_kcal_mol": final - initial, "energy_unit": "kcal/mol",
            "initial_sdf": initial_sdf, "sdf": sdf, "svg": svg_for(Chem.RemoveHs(final_mol)),
            "rdkit_version": info["rdkit_version"], "engine_provenance": "real",
            "energy_geometry": "exact serialized SDF coordinates",
            "scope": "Local force-field shape relaxation of one isolated molecule. Not a quantum calculation, reaction prediction, experimental measurement, or proof of a global minimum. Compare before and after for this same molecule only."}
