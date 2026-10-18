#!/usr/bin/env python3
"""Opt-in local checks and timings; never downloads, approves or executes ORCA."""
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=['core', 'engines', 'qwen', 'all'], default='core')
    parser.add_argument('--repeats', type=int, default=20)
    parser.add_argument('--output', type=Path, default=ROOT / 'benchmark-results')
    args = parser.parse_args()
    if not 1 <= args.repeats <= 10000:
        parser.error('--repeats must be 1..10000')
    out = args.output.resolve() / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'backend/src'), MPLBACKEND='Agg')
    report = {'schema': 'openchem.benchmark.v1', 'suite': args.suite,
              'started_utc': datetime.now(timezone.utc).isoformat(),
              'host': {'platform': platform.platform(), 'machine': platform.machine(),
                       'processor': platform.processor(), 'cpu_count': os.cpu_count(),
                       'python': sys.version}, 'checks': [], 'timings': [],
              'limits': 'Developer-visible integration/reference cases, not blind chemistry validation. Timings include software/runtime differences; compare matching versions and hardware.'}
    report['packages'] = {}
    for name in ['rdkit', 'numpy', 'scipy', 'matplotlib', 'fastapi', 'pytest']:
        try:
            report['packages'][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            report['packages'][name] = None

    def command(name, argv, timeout=900):
        started = time.perf_counter()
        try:
            completed = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout)
            log = completed.stdout + '\n' + completed.stderr
            status = 'PASS' if completed.returncode == 0 else 'FAIL'
            code = completed.returncode
        except (OSError, subprocess.TimeoutExpired) as exc:
            log, status, code = str(exc), 'FAIL', None
        (out / (name + '.log')).write_text(log, encoding='utf-8')
        report['checks'].append({'name': name, 'status': status, 'returncode': code,
                                 'wall_seconds': time.perf_counter() - started})
        print(name, status, flush=True)

    if args.suite in {'core', 'all'}:
        pytest_args = [sys.executable, '-m', 'pytest', '--rootdir', str(ROOT), 'backend/tests', '-q']
        # These three tests submit to a real isolated science worker. They are
        # outside the core-only package until that environment is installed.
        if args.suite == 'core' and not (ROOT / '.engines/science/bin/python').is_file():
            excluded = [
                'backend/tests/test_science_api.py::test_api_preview_execute_and_cancel_require_explicit_true',
                'backend/tests/test_science_jobs.py::test_science_requires_bound_single_use_approval_and_rejects_invalid_inputs',
                'backend/tests/test_science_jobs.py::test_real_numpy_and_pint_jobs_persist_reports_and_verify_project',
            ]
            report['not_run'] = [{'test': test, 'reason': 'Requires separately installed .engines/science environment'} for test in excluded]
            for test in excluded:
                pytest_args.extend(['--deselect', test])
            print('Core scope: 3 isolated-science tests NOT RUN; install engines for the full suite.', flush=True)
        command('backend-tests', pytest_args)
        node = shutil.which('node') or 'node'
        tests = sorted((ROOT / 'frontend/test/orca').glob('*.test.js')) + sorted((ROOT / 'frontend/test').glob('*.test.js'))
        command('frontend-tests', [node, '--test', *map(str, tests)])
        sys.path.insert(0, str(ROOT / 'backend/src'))
        try:
            from hypothesislab.conformers import molecule_conformer
            cases = [('water', 'O', [8, 1, 1]), ('ethanol', 'CCO', None), ('benzene', 'c1ccccc1', None)]
            for label, smiles, atoms in cases:
                molecule_conformer({'smiles': smiles, 'seed': 42})  # Unmeasured warmup.
                times = []
                for _ in range(args.repeats):
                    started = time.perf_counter()
                    result = molecule_conformer({'smiles': smiles, 'seed': 42})
                    times.append(time.perf_counter() - started)
                    assert result['converged'] and math.isfinite(result['energy'])
                    assert len(result['coordinates']) == len(result['atomic_numbers'])
                    if atoms:
                        assert result['atomic_numbers'] == atoms
                ordered = sorted(times)
                report['timings'].append({'case': 'rdkit-conformer-' + label, 'repeats': len(times),
                                          'min_seconds': min(times), 'median_seconds': statistics.median(times),
                                          'p95_seconds': ordered[math.ceil(.95 * len(times)) - 1],
                                          'seed': 42, 'force_field': result['force_field']})
            report['checks'].append({'name': 'conformer-reference-timings', 'status': 'PASS'})
        except Exception as exc:
            report['checks'].append({'name': 'conformer-reference-timings', 'status': 'FAIL', 'error': str(exc)})

    if args.suite in {'engines', 'all'}:
        command('science-operations', [sys.executable, 'scripts/test_science_engines.py'])
        command('extended-operations', [sys.executable, 'scripts/test_extended_engines.py', '--evidence', str(out / 'extended-runtime.json')])
        private = out / 'bioscience-work'; private.mkdir()
        command('bioscience-operations', [sys.executable, 'scripts/test_bioscience_engines.py', '--cwd', str(private), '--evidence', str(out / 'bioscience-runtime.json')])
        science = ROOT / 'evidence/science-runtime.json'
        if science.exists():
            shutil.copy2(science, out / 'science-runtime.json')

    if args.suite in {'qwen', 'all'}:
        sys.path.insert(0, str(ROOT / 'backend/src'))
        qwen_python = ROOT / '.venv-training/bin/python'
        prompts = [
            ('water', 'Build water O, charge 0, multiplicity 1, HF def2-SVP single point calculation.', 'H2O'),
            ('ethanol', 'Build ethanol CCO, charge 0, multiplicity 1, B3LYP def2-SVP optimization.', 'C2H6O'),
            ('benzene', 'Build benzene c1ccccc1, charge 0, multiplicity 1, B3LYP def2-SVP optimization and frequencies.', 'C6H6'),
        ]
        for label, prompt, formula in prompts:
            started = time.perf_counter()
            row = {'name': 'qwen-' + label, 'prompt': prompt}
            try:
                from hypothesislab.assistant import validate_draft, enforce_request
                completed = subprocess.run([str(qwen_python), '-m', 'hypothesislab.qwen_worker'],
                                           input=json.dumps({'prompt': prompt}), text=True, capture_output=True,
                                           cwd=ROOT, env=env, timeout=180)
                (out / ('qwen-' + label + '.log')).write_text(completed.stdout + '\n' + completed.stderr)
                if completed.returncode:
                    raise RuntimeError('Worker failed; see log')
                raw = json.loads(completed.stdout)
                row['worker'] = raw
                draft = validate_draft(raw['raw']); enforce_request(prompt, draft)
                assert draft['decision'] == 'proposal' and draft['validation']['formula'] == formula
                row.update(status='PASS', validated_draft=draft)
            except Exception as exc:
                row.update(status='FAIL', error=str(exc))
            row['wall_seconds'] = time.perf_counter() - started
            report['checks'].append(row)
            print(row['name'], row['status'], flush=True)

    report['status'] = 'PASS' if report['checks'] and all(c['status'] == 'PASS' for c in report['checks']) else 'FAIL'
    destination = out / 'result.json'
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print(report['status'], destination)
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
