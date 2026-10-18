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
