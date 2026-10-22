"""Versioned allowlist shared with an isolated worker; no engine imports here."""
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Annotated

Finite = Annotated[float, Field(allow_inf_nan=False, ge=-1e12, le=1e12)]
Vector = Annotated[list[Finite], Field(min_length=2, max_length=10000)]
Text = Annotated[str, Field(min_length=1, max_length=200000)]
class Inputs(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)
class Values(Inputs):
    values: Vector
    unit: Annotated[str, Field(min_length=1, max_length=80)]
class Formula(Inputs):
    formula: Annotated[str, Field(min_length=1, max_length=200)]
class Source(Inputs):
    source: Text
class Cell(Inputs):
    lattice: Annotated[list[Annotated[list[Finite], Field(min_length=3,max_length=3)]], Field(min_length=3,max_length=3)]
    positions: Annotated[list[Annotated[list[Finite], Field(min_length=3,max_length=3)]], Field(min_length=1,max_length=1000)]
    species: Annotated[list[Annotated[int,Field(ge=1,le=118)]],Field(min_length=1,max_length=1000)]
    symprec: Annotated[float,Field(gt=0,le=.1)] = 1e-5
    @model_validator(mode='after')
    def equal_length(self):
        if len(self.species)!=len(self.positions):raise ValueError('species and positions must have equal length')
        return self
class Convert(Inputs):
    value: Finite
    from_unit: Annotated[str,Field(min_length=1,max_length=80)]
    to_unit: Annotated[str,Field(min_length=1,max_length=80)]
class Line(Inputs):
    x: Vector
    y: Vector
    x_unit: Annotated[str,Field(min_length=1,max_length=80)]
    y_unit: Annotated[str,Field(min_length=1,max_length=80)]
    @model_validator(mode='after')
    def matching(self):
        if len(self.x)!=len(self.y) or len(self.x)<3 or len(set(self.x))<2:raise ValueError('Use at least three paired observations and distinct x values')
        return self
class FID(Inputs):
    real: Vector
    imag: Vector
    dwell_s: Annotated[float,Field(gt=0,le=100)]
    @model_validator(mode='after')
    def matching(self):
        if len(self.real)!=len(self.imag):raise ValueError('Real and imaginary lengths differ')
        return self
class Sequence(Inputs):
    sequence: Annotated[str,Field(min_length=1,max_length=100000)]
class Optimize(Inputs):
    center: Annotated[float,Field(ge=-5,le=5)]
    trials: Annotated[int,Field(ge=1,le=100)] = 32
class Gas(Inputs):
    temperature_K: Annotated[float,Field(ge=300,le=3000)]
    pressure_Pa: Annotated[float,Field(ge=1000,le=1e7)]
    composition: Annotated[str,Field(min_length=1,max_length=200)]
class Harmonic(Inputs):
    distance_nm: Annotated[float,Field(gt=0,le=10)]
    equilibrium_nm: Annotated[float,Field(gt=0,le=10)]
    k_kJ_mol_nm2: Annotated[float,Field(gt=0,le=1e6)]
class Trajectory(Inputs):
    coordinates_nm: Annotated[list[Annotated[list[Finite],Field(min_length=3,max_length=3)]],Field(min_length=2,max_length=1000)]
class Provenance(Inputs):
    name: Annotated[str,Field(min_length=1,max_length=100)]
class Molecule(Inputs):
    smiles: Annotated[str,Field(min_length=1,max_length=5000)]
# operation -> (engine, input contract, label, units, scientific limitations)
OPERATIONS = {
 'numpy.summary': ('NumPy',Values,'Summarize numerical observations','Input unit; population standard deviation (ddof=0)','Descriptive statistics; no uncertainty model'),
 'scipy.line': ('SciPy',Line,'Fit a straight line','Explicit x/y units','Unweighted independent errors; not causal inference'),
 'gemmi.cif': ('Gemmi',Source,'Inspect a small-molecule CIF','Cell lengths angstrom; volume angstrom^3','One CIF block; no refinement or experimental validation'),
 'spglib.symmetry': ('Spglib',Cell,'Find crystal symmetry','Lattice angstrom; positions fractional; tolerance angstrom','Symmetry depends on supplied cell and tolerance'),
 'pymatgen.composition': ('Pymatgen',Formula,'Analyze a composition','Atomic mass in unified atomic mass units','Formula composition only; no structure or stability calculation'),
 'pymatgencore.composition': ('PymatgenCore',Formula,'Analyze a composition with pymatgen-core','Atomic mass in unified atomic mass units','Shared pymatgen.core runtime; not an independent algorithm'),
 'pint.convert': ('Pint',Convert,'Convert compatible physical units','Explicit source and destination units','Dimensional conversion; does not verify measurement correctness'),
 'pandas.csv': ('Pandas',Source,'Inspect a CSV table','Original column values; no assumed units','Missing entries reported; source bytes preserved'),
 'polars.csv': ('Polars',Source,'Inspect a CSV table with Polars','Original column values; no assumed units','Schema inspection only; source bytes preserved'),
 'lmfit.line': ('lmfit',Line,'Fit a line with lmfit','Explicit x/y units','Unweighted least squares; covariance may be unavailable'),
 'nmrglue.fft': ('nmrglue',FID,'Fourier transform a complex FID','Dwell seconds; frequency Hz; amplitude arbitrary input units','No phase, baseline, referencing or physical peak assignment'),
 'pyteomics.mass': ('Pyteomics',Formula,'Calculate formula monoisotopic mass','Unified atomic mass units','Neutral formula; isotope assumptions from Pyteomics defaults'),
 'biopython.dna': ('Biopython',Sequence,'Inspect a DNA sequence','Base counts and GC fraction','ACGT only; no clinical interpretation'),
 'optuna.quadratic': ('Optuna',Optimize,'Demonstrate seeded experimental search','Synthetic dimensionless objective','Synthetic (x-center)^2 on [-5,5]; no laboratory prediction'),
 'cantera.equilibrium': ('Cantera',Gas,'Equilibrate a gas mixture at fixed T/P','Temperature K; pressure Pa; mole fractions','Bundled GRI-Mech 3.0 mechanism only; ideal gas; no kinetic time prediction'),
 'openmm.harmonic': ('OpenMM',Harmonic,'Evaluate a two-particle harmonic bond','Distance nm; energy kJ/mol','Reference CPU platform; synthetic bonded pair; no force field inference'),
 'mdtraj.distance': ('MDTraj',Trajectory,'Measure distances along a trajectory','Coordinates nm; distance nm','Two atoms represented by the supplied consecutive coordinate pairs'),
 'mdanalysis.geometry': ('MDAnalysis',Trajectory,'Measure radius of gyration','Input nm converted to angstrom internally; output nm','Equal synthetic carbon masses; one supplied configuration'),
 'rocrate.manifest': ('ROCratePy',Provenance,'Create a research-object metadata manifest','JSON-LD schema.org terms','Metadata document only; external resources are not fetched'),
 'ord.reaction': ('ORDschema',Molecule,'Create an ORD reaction record from a reactant','SMILES input; serialized JSON','Schema serialization only; no reaction outcome predicted'),
}

# Small, deterministic inputs used by the UI and the isolated runtime verifier.
# They are examples, not experimental reference data or scientific validation.
EXAMPLES = {
 'numpy.summary': {'values':[1.0,2.0,3.0], 'unit':'a.u.'},
 'scipy.line': {'x':[0.0,1.0,2.0,3.0], 'y':[1.0,3.0,5.0,7.0], 'x_unit':'s', 'y_unit':'a.u.'},
 'gemmi.cif': {'source':"""data_NaCl
_cell_length_a 5.64
_cell_length_b 5.64
_cell_length_c 5.64
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_space_group_name_H-M_alt 'F m -3 m'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Na1 Na 0 0 0
Cl1 Cl 0.5 0.5 0.5
"""},
 'spglib.symmetry': {'lattice':[[5.64,0.0,0.0],[0.0,5.64,0.0],[0.0,0.0,5.64]],
                      'positions':[[0,0,0],[0,.5,.5],[.5,0,.5],[.5,.5,0],[.5,.5,.5],[.5,0,0],[0,.5,0],[0,0,.5]],
                      'species':[11,11,11,11,17,17,17,17], 'symprec':1e-5},
 'pymatgen.composition': {'formula':'NaCl'},
 'pymatgencore.composition': {'formula':'NaCl'},
 'pint.convert': {'value':1000.0, 'from_unit':'milligram', 'to_unit':'gram'},
 'pandas.csv': {'source':'time,signal\n0,1\n1,3\n2,5\n'},
 'polars.csv': {'source':'time,signal\n0,1\n1,3\n2,5\n'},
 'lmfit.line': {'x':[0.0,1.0,2.0,3.0], 'y':[1.0,3.0,5.0,7.0], 'x_unit':'s', 'y_unit':'a.u.'},
 'nmrglue.fft': {'real':[1.0,0.0,-1.0,0.0], 'imag':[0.0,1.0,0.0,-1.0], 'dwell_s':0.001},
 'pyteomics.mass': {'formula':'H2O'},
 'biopython.dna': {'sequence':'ATGC'},
 'optuna.quadratic': {'center':1.25, 'trials':16},
 'cantera.equilibrium': {'temperature_K':1000.0, 'pressure_Pa':101325.0, 'composition':'CH4:1, O2:2, N2:7.52'},
 'openmm.harmonic': {'distance_nm':0.2, 'equilibrium_nm':0.1, 'k_kJ_mol_nm2':100.0},
 'mdtraj.distance': {'coordinates_nm':[[0,0,0],[1,0,0],[0,0,0],[2,0,0]]},
 'mdanalysis.geometry': {'coordinates_nm':[[0,0,0],[2,0,0]]},
 'rocrate.manifest': {'name':'Chem313 runtime example'},
 'ord.reaction': {'smiles':'CCO'},
}

def validate_operation(operation, inputs):
    if not isinstance(operation,str) or operation not in OPERATIONS:raise ValueError('Operation is not in the scientific allowlist')
    return OPERATIONS[operation][1].model_validate(inputs).model_dump()

def descriptions():
    return [dict(schema='openchem.capability.v1',input_formats=['application/json'] + (['text/csv'] if key in {'pandas.csv','polars.csv'} else ['chemical/x-cif'] if key=='gemmi.cif' else []),output_formats=['application/json'],source_preservation='Exact request JSON and supplied source text saved before execution',operation=key,engine=v[0],label=v[2],input_schema=v[1].model_json_schema(),example=EXAMPLES[key],units=v[3],limitations=v[4],effect='project_write',resources={'cpu_threads':1,'wall_seconds':120,'max_output_bytes':1000000,'gpu':False,'memory':'Observed RSS recorded; no hardened memory sandbox'}) for key,v in OPERATIONS.items()]
