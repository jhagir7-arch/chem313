"""Record bundled engine identities without private acquisition catalogs."""
import importlib.metadata as metadata
import json
from pathlib import Path
import sys

engines = []
for name, package, domain, repo, license_name, operations in [
    ("RDKit", "rdkit", "cheminformatics", "rdkit/rdkit", "BSD-3-Clause", ["molecule.inspect_smiles", "molecule.import_molfile", "molecule.fidelity_audit", "molecule.generate_conformer"]),
    ("NumPy", "numpy", "numerical_analysis", "numpy/numpy", "BSD-3-Clause and bundled notices", ["numpy.summary"]),
    ("SciPy", "scipy", "measurement_analysis", "scipy/scipy", "BSD-3-Clause and bundled notices", ["scipy.line", "measurement.fit_csv"]),
    ("Matplotlib", "matplotlib", "plotting", "matplotlib/matplotlib", "Matplotlib license and bundled notices", ["measurement.fit_csv"]),
]:
    engines.append(dict(name=name, version=metadata.version(package), domain=domain,
                        repo="https://github.com/" + repo, license=license_name, operations=operations))
for name, package, domain, repo, license_name, operations in [
    ("Ketcher", "ketcher-react", "molecular_editing", "epam/ketcher", "Apache-2.0", ["local molecular drawing"]),
    ("Indigo", "indigo-ketcher", "structure_service", "epam/Indigo", "Apache-2.0", ["Ketcher standalone structure service"]),
    ("3DmolJS", "3dmol", "molecular_visualization", "3dmol/3Dmol.js", "BSD-3-Clause", ["local molecular WebGL view"]),
]:
    package_json = json.loads((Path("frontend/node_modules") / package / "package.json").read_text())
    engines.append(dict(name=name, version=package_json["version"], domain=domain,
                        repo="https://github.com/" + repo, license=license_name, operations=operations))
profile = dict(schema="openchem.standalone.v1", distribution="1.0.0-preview.5-standalone", architecture="arm64",
               minimum_macos="14.0", operations=["numpy.summary", "scipy.line"], engines=engines)
Path(sys.argv[1]).write_text(json.dumps(profile, indent=2) + "\n")
