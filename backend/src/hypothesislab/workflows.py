"""Conservative offline intent selection. Suggestions cannot execute an action.

This deliberately small interpreter is not a trained language model. The D-001
prototype's separation between plans and approvals is retained; trained model
weights and production evaluation are not supplied by the handoff datasets.
"""
import re
from .science_jobs import operation_descriptions


def plan(text):
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        raise ValueError("Describe a goal using 1–4000 characters")
    lower = text.casefold()
    available = {x["operation"]: x for x in operation_descriptions()}
    candidates = []
    rules = [
        ("pint.convert", r"\b(convert|conversion)\b.*\b(unit|kelvin|celsius|joule|kcal|angstrom|nm|meter|metre|kj|ev)"),
        ("scipy.line", r"\b(linear|straight line|regression)\b"),
        ("numpy.summary", r"\b(mean|average|standard deviation|summari[sz]e)\b"),
        ("gemmi.cif", r"\bcif\b"),
        ("spglib.symmetry", r"\b(crystal symmetry|space group|spacegroup)\b"),
        ("pymatgen.composition", r"\b(composition|formula weight|molar mass)\b"),
        ("pandas.csv", r"\b(csv|table columns|missing values)\b"),
        ("nmrglue.fft", r"\b(fid|fourier|fft)\b"),
        ("pyteomics.mass", r"\b(monoisotopic|exact mass)\b"),
        ("biopython.dna", r"\b(dna|gc fraction|reverse complement)\b"),
        ("cantera.equilibrium", r"\b(gas equilibrium|equilibrate gas|gas mixture)\b"),
        ("openmm.harmonic", r"\bharmonic bond\b"),
        ("mdtraj.distance", r"\b(trajectory distance|distances along)\b"),
        ("mdanalysis.geometry", r"\bradius of gyration\b"),
        ("rocrate.manifest", r"\b(ro-crate|research object|metadata manifest)\b"),
        ("ord.reaction", r"\b(ord|reaction record)\b"),
        ("optuna.quadratic", r"\b(synthetic optimi[sz]ation|quadratic)\b"),
        ("pyscf.rhf_singlepoint", r"\b(pyscf|hartree.fock|rhf)\b|\b(h2|hydrogen)\b.*\b(hartree|quantum|energy)\b"),
        ("tblite.gfn2_singlepoint", r"\b(tblite|gfn2|gfn2.xtb)\b"),
        ("matchms.cosine_greedy", r"\b(matchms|spectral cosine|compare mass spectra)\b"),
        ("meeko.prepare_pdbqt", r"\b(meeko|prepare pdbqt|ligand preparation)\b"),
        ("pyenzyme.document", r"\b(enzymeml|pyenzyme)\b"),
        ("pysb.first_order_decay", r"\b(pysb|first.order decay)\b"),
    ]
    for op, pattern in rules:
        if op in available and re.search(pattern, lower):
            candidates.append(op)
    # No fake experimental inputs, named molecules, files, units or success.
    base = {"requires_explicit_apply": True, "planner": "offline rules v1; no LLM configured", "executes": False}
    if len(candidates) != 1:
        return dict(base, status="UNSUPPORTED" if not candidates else "NEEDS_INPUT",
                    message="Choose a supported operation below, or describe one goal more precisely. No computation has run.", candidates=candidates)
    op = candidates[0]
    description = available[op]
    if op == "pint.convert":
        conversion = re.fullmatch(r"\s*convert\s+([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)\s+([a-z°_/*^().+\-0-9 ]{1,80}?)\s+to\s+([a-z°_/*^().+\-0-9 ]{1,80})\s*[?.]?", lower)
        if conversion:
            value = float(conversion[1])
            if abs(value) <= 1e12:
                return dict(base, status="PROPOSED", operation=op, inputs=dict(value=value, from_unit=conversion[2].strip(), to_unit=conversion[3].strip()),
                            message="Prepared the conversion using the number and units in your request. Preview and apply it to run Pint; no result has been calculated.")
    return dict(base, status="NEEDS_INPUT", operation=op,
                message=f"Suggested: {description['label']} using {description['engine']}. Supply and review the actual inputs before running; the displayed example is synthetic.",
                required_inputs=description["input_schema"].get("required", []))
