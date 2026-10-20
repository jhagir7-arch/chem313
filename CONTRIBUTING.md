# Contributing to Chem313

Chem313 is a research preview. Use [GitHub Issues](https://github.com/jhagir7-arch/openchem/issues) for all public questions, bug reports, and proposals. Do not post private research data, credentials, proprietary engine files, or personal paths.

## Start small

Good first contributions include:

- improve a beginner workflow, labels, error messages, or keyboard navigation;
- add or improve a focused frontend or backend test; and
- file a reproducible issue with the steps, expected result, actual result, platform, and preview version.

Before opening a change, set up the checked-in runtime and run the same core checks used by this repository:

```sh
bash scripts/setup_public_runtime.sh
npm --prefix frontend test
npm --prefix frontend run build
python3 scripts/check_project_index.py
```

The setup script requires Python 3.13 and Node 24.20 or later. Use synthetic or rights-cleared examples in reports and tests.

## Chemistry review

Chemistry-domain contributions should identify the source or method, inputs, units, assumptions, and the limit of the proposed interpretation. Check that molecule identity, charge, multiplicity, geometry, method labels, and energy units are represented consistently. A successful process or rendered result does not establish convergence, a quantum calculation, experimental agreement, or scientific validity.

ORCA and Q-Chem are separately licensed external engines. Do not add their binaries, licensed inputs or outputs, or claims that a real job ran without reproducible evidence from an authorized installation.

## Native, platform, and release work

Keep platform changes scoped to a named target and report the actual OS, architecture, toolchain, and checks run. The Mac preview is ad-hoc signed and not notarized; do not describe it as Developer ID signed or notarized without the corresponding verification. Windows and Linux downloads remain gated on their native smoke tests, notice capture, and redistribution review.

Preserve copyright and third-party notices. Contributions are submitted under [Apache-2.0](LICENSE) unless a separate written agreement applies. Identify copied or adapted material and its source and license. Do not submit code, data, dependencies, binaries, or model assets unless you have authority to contribute and redistribute them.

See [community guidance](docs/COMMUNITY.md), [release scope](release/public-source/PUBLICATION_STATUS.md), and [third-party notices](THIRD_PARTY_NOTICES.md).
