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


# Backwards-compatible alias; the catalog is the source of truth.
from .catalog import FORCE_FIELDS, RELAXATION, STARTERS, starter_name  # noqa: E402

FIRST_MOLECULES = {m["smiles"]: m["name"] for m in STARTERS[:3]}

_LIMITS = RELAXATION["limits"]
_DEFAULTS = RELAXATION["defaults"]


def _molecule_from_params(params: dict):
    """Build the RDKit molecule (topology only) from smiles or molblock; raise ValueError on anything odd."""
    Chem = _dependency("rdkit.Chem", "geometry relaxation")
    if "smiles" in params:
        text = params["smiles"]
        if not isinstance(text, str) or not text.strip() or len(text) > 5000:
            raise ValueError("smiles must be a non-empty string")
        mol = Chem.MolFromSmiles(text)
        if mol is None:
            raise ValueError("That SMILES could not be read.")
    else:
        text = params["molblock"]
        if not isinstance(text, str) or not text.strip() or len(text) > 250_000:
            raise ValueError("molblock must be a non-empty string")
        records = text.split("$$$$")
        if any(record.strip() for record in records[1:]):
            raise ValueError("Structure files must contain exactly one molecule; select a single record.")
        mol = Chem.MolFromMolBlock(records[0])
        if mol is None:
            raise ValueError("That structure could not be read.")
    if len(Chem.GetMolFrags(mol)) != 1:
        raise ValueError("One connected molecule at a time; remove the extra fragments.")
    if any(stereo.specified == Chem.StereoSpecified.Unspecified for stereo in Chem.FindPotentialStereo(mol)):
        raise ValueError("Specify stereochemistry for all potential stereocenters and double bonds before relaxation.")
    if mol.GetNumHeavyAtoms() == 0:
        raise ValueError("Add at least one heavy atom.")
    if mol.GetNumHeavyAtoms() > _LIMITS["heavy_atoms"]["max"]:
        raise ValueError(f"Up to {_LIMITS['heavy_atoms']['max']} heavy atoms are supported here.")
    return mol


def validate_relaxation(params: dict) -> None:
    if not isinstance(params, dict):
        raise ValueError("Parameters must be an object")
    unknown = set(params) - {"smiles", "molblock", "seed", "force_field", "max_iterations", "name"}
    if unknown:
        raise ValueError("Unexpected parameter: " + ", ".join(sorted(unknown)))
    if ("smiles" in params) == ("molblock" in params):
        raise ValueError("Give exactly one of smiles or molblock.")
    seed = params.get("seed", _DEFAULTS["seed"])
    if isinstance(seed, bool) or not isinstance(seed, int) or not _LIMITS["seed"]["min"] <= seed <= _LIMITS["seed"]["max"]:
        raise ValueError(f"seed must be an integer from {_LIMITS['seed']['min']} through {_LIMITS['seed']['max']}")
    iterations = params.get("max_iterations", _DEFAULTS["max_iterations"])
    if isinstance(iterations, bool) or not isinstance(iterations, int) or not _LIMITS["max_iterations"]["min"] <= iterations <= _LIMITS["max_iterations"]["max"]:
        raise ValueError(f"max_iterations must be an integer from {_LIMITS['max_iterations']['min']} through {_LIMITS['max_iterations']['max']}")
    force_field = params.get("force_field", _DEFAULTS["force_field"])
    if force_field not in FORCE_FIELDS:
        raise ValueError("force_field must be one of " + ", ".join(FORCE_FIELDS))
    if "name" in params and (not isinstance(params["name"], str) or len(params["name"]) > 80):
        raise ValueError("name must be a string of up to 80 characters")
    mol = _molecule_from_params(params)
    Chem = _dependency("rdkit.Chem", "geometry relaxation")
    AllChem = _dependency("rdkit.Chem.AllChem", "force-field relaxation")
    with_hydrogens = Chem.AddHs(mol)
    has_params = (AllChem.UFFHasAllMoleculeParams(with_hydrogens) if force_field == "UFF"
                  else AllChem.MMFFHasAllMoleculeParams(with_hydrogens))
    if not has_params:
        raise ValueError(f"{force_field} parameters are unavailable for this structure.")


def _force_field(AllChem, mol, name: str):
    if name == "UFF":
        if not AllChem.UFFHasAllMoleculeParams(mol):
            raise ValueError("UFF parameters are unavailable for this structure.")
        return AllChem.UFFGetMoleculeForceField(mol)
    props = AllChem.MMFFGetMoleculeProperties(mol, mmffVariant="MMFF94")
    if props is None:
        raise ValueError("MMFF94 parameters are unavailable for this structure.")
    return AllChem.MMFFGetMoleculeForceField(mol, props)


def relax_geometry(params: dict) -> dict:
    """Real, reproducible force-field relaxation; energies refer to exact saved geometries."""
    import math
    from .chemistry import summary, svg_for
    validate_relaxation(params)
    Chem = _dependency("rdkit.Chem", "geometry relaxation")
    AllChem = _dependency("rdkit.Chem.AllChem", "force-field relaxation")
    seed = params.get("seed", _DEFAULTS["seed"])
    force_field = params.get("force_field", _DEFAULTS["force_field"])
    max_iterations = params.get("max_iterations", _DEFAULTS["max_iterations"])
    topology = _molecule_from_params(params)
    canonical = Chem.MolToSmiles(topology)
    expected_key = Chem.MolToInchiKey(topology)
    mol = Chem.AddHs(topology)
    embed = AllChem.ETKDGv3()
    embed.randomSeed = seed
    if AllChem.EmbedMolecule(mol, embed) < 0:
        raise ValueError("The starting shape could not be generated. Try another seed or molecule.")
    # Round-trip before evaluating so another program can reproduce the exact energy
    # from the exported SDF rather than unavailable full-precision coordinates.
    initial_sdf = Chem.MolToMolBlock(mol) + "$$$$\n"
    mol = Chem.MolFromMolBlock(initial_sdf.split("$$$$")[0], removeHs=False)
    ff = _force_field(AllChem, mol, force_field)
    initial_key = Chem.MolToInchiKey(mol)
    initial = float(ff.CalcEnergy())
    code = int(ff.Minimize(maxIts=max_iterations, forceTol=_LIMITS["force_tolerance"], energyTol=_LIMITS["energy_tolerance"]))
    sdf = Chem.MolToMolBlock(mol) + "$$$$\n"
    final_mol = Chem.MolFromMolBlock(sdf.split("$$$$")[0], removeHs=False)
    final = float(_force_field(AllChem, final_mol, force_field).CalcEnergy())
    if not all(math.isfinite(value) for value in (initial, final)):
        raise ValueError("The calculation returned an invalid energy; no result was saved.")
    final_key = Chem.MolToInchiKey(final_mol)
    if not expected_key or initial_key != expected_key or final_key != expected_key:
        raise ValueError("The saved structure no longer matches the drawn molecule.")
    info = summary(final_mol)
    name = params.get("name") or starter_name(canonical) or info["formula"]
    return {"schema": "chem313.geometry-relaxation.v1", "name": name,
            "smiles": params.get("smiles", canonical), "canonical_smiles": canonical,
            "formula": info["formula"], "atom_count": final_mol.GetNumAtoms(),
            "formal_charge": int(Chem.GetFormalCharge(final_mol)),
            "inchikey": expected_key, "identity_status": "MATCH", "seed": seed,
            "embedding": RELAXATION["embedding"], "force_field": force_field, "iterations_limit": max_iterations,
            "force_tolerance": _LIMITS["force_tolerance"], "energy_tolerance": _LIMITS["energy_tolerance"],
            "converged": code == 0, "convergence_status": code,
            "initial_energy_kcal_mol": initial, "final_energy_kcal_mol": final,
            "energy_change_kcal_mol": final - initial, "energy_unit": "kcal/mol",
            "initial_sdf": initial_sdf, "sdf": sdf, "svg": svg_for(Chem.RemoveHs(final_mol)),
            "rdkit_version": info["rdkit_version"], "engine_provenance": "real",
            "energy_geometry": "exact serialized SDF coordinates",
            "scope": RELAXATION["scope"]}
