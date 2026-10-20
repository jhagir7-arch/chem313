"""Isolated, lazy scientific worker. Input is JSON, never source code or shell."""
import contextlib
import importlib.metadata as metadata
import io
import json
import math
import os
import sys
import time
from .science_contracts import OPERATIONS, validate_operation

try:
    import resource
except ImportError:  # Windows has no POSIX rlimit API.
    resource = None

DISTRIBUTIONS={'PymatgenCore':'pymatgen-core','ROCratePy':'rocrate','ORDschema':'ord-schema','Biopython':'biopython'}


def resource_limits() -> dict:
    if resource is None:
        return {'cpu': 'UNAVAILABLE_ON_PLATFORM', 'file_size': 'UNAVAILABLE_ON_PLATFORM'}
    resource.setrlimit(resource.RLIMIT_CPU, (110, 115))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1_500_000, 1_500_000))
    return {'cpu': 'POSIX_RLIMIT_ENFORCED', 'file_size': 'POSIX_RLIMIT_ENFORCED'}


def resource_usage() -> tuple[float | None, int | None]:
    if resource is None:
        return None, None
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # macOS reports bytes; Linux reports KiB. Preserve the public bytes field.
    max_rss_bytes = usage.ru_maxrss * 1024 if sys.platform.startswith('linux') else usage.ru_maxrss
    return usage.ru_utime, max_rss_bytes

def run(op,p):
    if op=='numpy.summary':
        import numpy as np
        a=np.asarray(p['values'],dtype=float)
        return dict(count=len(a),mean=float(a.mean()),standard_deviation=float(a.std()),minimum=float(a.min()),maximum=float(a.max()),unit=p['unit'])
    if op=='scipy.line':
        from scipy.stats import linregress
        r=linregress(p['x'],p['y']);return dict(slope=float(r.slope),intercept=float(r.intercept),r_squared=float(r.rvalue**2),slope_standard_error=float(r.stderr),x_unit=p['x_unit'],y_unit=p['y_unit'])
    if op=='gemmi.cif':
        import gemmi
        s=gemmi.make_small_structure_from_block(gemmi.cif.read_string(p['source']).sole_block())
        if not s.cell.is_crystal() or not len(s.sites):raise ValueError('CIF requires a valid crystal cell and atom sites')
        return dict(name=s.name,cell_angstrom_degrees=s.cell.parameters,volume_angstrom3=s.cell.volume,sites=len(s.sites),spacegroup=s.spacegroup_hm)
    if op=='spglib.symmetry':
        import numpy as np,spglib
        if abs(np.linalg.det(p['lattice']))<1e-10:raise ValueError('Lattice is singular')
        d=spglib.get_symmetry_dataset((p['lattice'],p['positions'],p['species']),symprec=p['symprec'])
        if d is None:raise ValueError('No symmetry dataset for this cell')
        return dict(number=d.number,international=d.international,hall=d.hall,rotations=len(d.rotations),symprec_angstrom=p['symprec'])
    if op in {'pymatgen.composition','pymatgencore.composition'}:
        from pymatgen.core import Composition
        c=Composition(p['formula']);return dict(reduced_formula=c.reduced_formula,elements=c.get_el_amt_dict(),mass_u=float(c.weight))
    if op=='pint.convert':
        import pint,re
        if any(not re.fullmatch(r'[A-Za-z0-9_ °/*^().+\-]{1,80}',p[x]) for x in ['from_unit','to_unit']):raise ValueError('Unsupported unit expression')
        u=pint.UnitRegistry();q=u.Quantity(p['value'],p['from_unit']).to(p['to_unit']);return dict(value=float(q.magnitude),unit=str(q.units))
    if op in {'pandas.csv','polars.csv'}:
        import csv
        rows=list(csv.reader(io.StringIO(p['source']),strict=True))
        if not rows or not rows[0] or len(rows)>10001 or len(set(x.casefold() for x in rows[0]))!=len(rows[0]) or any(not x.strip() for x in rows[0]) or any(len(x)!=len(rows[0]) for x in rows[1:]):raise ValueError('CSV must have unique headings and consistent rows; limit 10000 rows')
        if op=='pandas.csv':
            import pandas as pd
            f=pd.read_csv(io.StringIO(p['source']));return dict(rows=len(f),columns=[dict(name=str(k),dtype=str(v),missing=int(f[k].isna().sum())) for k,v in f.dtypes.items()])
        import polars as pl
        f=pl.read_csv(io.StringIO(p['source']));return dict(rows=f.height,columns=[dict(name=k,dtype=str(v),missing=f[k].null_count()) for k,v in f.schema.items()])
    if op=='lmfit.line':
        import numpy as np
        from lmfit.models import LinearModel
        model=LinearModel();x=np.asarray(p['x']);y=np.asarray(p['y']);r=model.fit(y,model.guess(y,x=x),x=x)
        if not r.success:raise ValueError('lmfit did not converge')
        return dict(slope=r.params['slope'].value,intercept=r.params['intercept'].value,chisqr=r.chisqr,converged=r.success,x_unit=p['x_unit'],y_unit=p['y_unit'])
    if op=='nmrglue.fft':
        import numpy as np,nmrglue as ng
        a=np.asarray(p['real'])+1j*np.asarray(p['imag']);z=ng.proc_base.fft(a);freq=np.fft.fftshift(np.fft.fftfreq(len(a),p['dwell_s']))
        return dict(frequency_Hz=freq.tolist(),real=z.real.tolist(),imag=z.imag.tolist(),normalization='nmrglue.proc_base.fft defaults')
    if op=='pyteomics.mass':
        from pyteomics import mass
        return dict(formula=p['formula'],monoisotopic_mass_u=mass.calculate_mass(formula=p['formula']))
    if op=='biopython.dna':
        from Bio.Seq import Seq
        from Bio.SeqUtils import gc_fraction
        s=p['sequence'].upper()
        if set(s)-set('ACGT'):raise ValueError('Use unambiguous ACGT DNA bases only')
        a=Seq(s);return dict(length=len(a),gc_fraction=gc_fraction(a),reverse_complement=str(a.reverse_complement()))
    if op=='optuna.quadratic':
        import optuna
        optuna.logging.set_verbosity(optuna.logging.ERROR)
        s=optuna.create_study(sampler=optuna.samplers.TPESampler(seed=42));s.optimize(lambda t:(t.suggest_float('x',-5,5)-p['center'])**2,n_trials=p['trials'])
        return dict(best_x=s.best_params['x'],objective=s.best_value,trials=len(s.trials),seed=42,synthetic=True)
    if op=='cantera.equilibrium':
        import cantera as ct
        g=ct.Solution('gri30.yaml');g.TPX=p['temperature_K'],p['pressure_Pa'],p['composition'];before={e:g.elemental_mass_fraction(e) for e in g.element_names};g.equilibrate('TP',max_steps=1000)
        return dict(temperature_K=g.T,pressure_Pa=g.P,mole_fractions={s:float(x) for s,x in zip(g.species_names,g.X) if x>1e-12},element_mass_fractions_before=before,element_mass_fractions_after={e:g.elemental_mass_fraction(e) for e in g.element_names},mechanism='GRI-Mech 3.0',converged=True)
    if op=='openmm.harmonic':
        import openmm as mm
        from openmm import unit
        s=mm.System();s.addParticle(12);s.addParticle(12);b=mm.HarmonicBondForce();b.addBond(0,1,p['equilibrium_nm'],p['k_kJ_mol_nm2']);s.addForce(b)
        integ=mm.VerletIntegrator(.001);c=mm.Context(s,integ,mm.Platform.getPlatformByName('Reference'));c.setPositions([[0,0,0],[p['distance_nm'],0,0]])
        return dict(energy_kJ_mol=c.getState(getEnergy=True).getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole),platform=c.getPlatform().getName(),particles=2)
    if op=='mdtraj.distance':
        import mdtraj as md,numpy as np
        xyz=np.asarray(p['coordinates_nm']);
        if len(xyz)%2:raise ValueError('Use an even number of coordinates, two atoms per frame')
        top=md.Topology();chain=top.add_chain();res=top.add_residue('PAIR',chain);top.add_atom('C1',md.element.carbon,res);top.add_atom('C2',md.element.carbon,res)
        t=md.Trajectory(xyz.reshape(-1,2,3),top);return dict(distances_nm=md.compute_distances(t,[[0,1]],periodic=False)[:,0].tolist(),frames=len(t))
    if op=='mdanalysis.geometry':
        import MDAnalysis as mda,numpy as np
        a=np.asarray(p['coordinates_nm'])*10;u=mda.Universe.empty(len(a),trajectory=True);u.add_TopologyAttr('masses',np.full(len(a),12.0));u.atoms.positions=a
        return dict(radius_of_gyration_nm=float(u.atoms.radius_of_gyration()/10),atoms=len(a),mass_assumption='equal carbon masses')
    if op=='rocrate.manifest':
        from rocrate.rocrate import ROCrate
        r=ROCrate();r.name=p['name'];return dict(manifest=r.metadata.generate())
    if op=='ord.reaction':
        from ord_schema.proto import reaction_pb2
        from google.protobuf.json_format import MessageToDict
        r=reaction_pb2.Reaction();r.inputs['reactant'].components.add().identifiers.add(type=reaction_pb2.CompoundIdentifier.SMILES,value=p['smiles'])
        return dict(reaction=MessageToDict(r,preserving_proto_field_name=True),validation_scope='serialization only; incomplete reaction record')
    raise ValueError('Unimplemented operation')

def main():
    start=time.monotonic()
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','RAYON_NUM_THREADS','POLARS_MAX_THREADS','VECLIB_MAXIMUM_THREADS'):
        os.environ[key]='1'
    # The parent enforces wall time and result acceptance size on every OS.
    # POSIX CPU/file limits add defense in depth where the platform provides them.
    limits = resource_limits()
    try:
        raw=sys.stdin.buffer.read(250001)
        if len(raw)>250000:raise ValueError('Input exceeds 250 KB')
        request=json.loads(raw);op=request['operation'];p=validate_operation(op,request['inputs'])
        with contextlib.redirect_stdout(sys.stderr):result=run(op,p)
        engine=OPERATIONS[op][0];dist=DISTRIBUTIONS.get(engine,engine)
        user_cpu_seconds, max_rss_bytes = resource_usage()
        result=dict(schema='openchem.science.result.v1',operation=op,engine=engine,version=metadata.version(dist),output=result,units=OPERATIONS[op][3],limitations=OPERATIONS[op][4],resources=dict(wall_seconds=time.monotonic()-start,user_cpu_seconds=user_cpu_seconds,max_rss_bytes=max_rss_bytes,gpu=False,threads=1,limits=limits))
        encoded=json.dumps(result,allow_nan=False)
        if len(encoded.encode())>1000000:raise ValueError('Result exceeds 1 MB cap')
        print(encoded)
    except Exception as e:
        print(json.dumps(dict(status='FAILED',error=f'{type(e).__name__}: {e}')));raise SystemExit(2)
if __name__=='__main__':main()
