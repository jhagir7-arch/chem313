# Chem313 preview.6 — your first real molecule calculation

Chem313 preview.6 makes one complete beginner job available: choose a small molecule, relax its shape with the included MMFF94 force field, inspect the 3D result and energy chart, and save a reproducible record. No Python, Node, engine account or Qwen setup is required.

## Downloads

- Windows x64: [portable ZIP](https://github.com/jhagir7-arch/chem313/releases/download/v1.0.0-preview.6/Chem313-core-windows-amd64.zip). Extract the entire folder, then open Chem313.exe. Supports Windows 10 or later / Server 2022 or later; native automated checks ran on Server 2022.
- Linux x86_64: [portable archive](https://github.com/jhagir7-arch/chem313/releases/download/v1.0.0-preview.6/Chem313-core-linux-x86_64.tar.gz). Extract the entire folder, then run ./Chem313. Tested on Ubuntu 22.04; requires glibc 2.35 or later. Other distributions and ARM systems have not been verified.
- Apple Silicon Mac, macOS 14+: [DMG](https://github.com/jhagir7-arch/chem313/releases/download/v1.0.0-preview.6/Chem313-1.0.0-preview.6-Mac-arm64.dmg) or [ZIP](https://github.com/jhagir7-arch/chem313/releases/download/v1.0.0-preview.6/Chem313-1.0.0-preview.6-Mac-arm64.zip). Ad-hoc signed, not Apple Developer ID signed or notarized; macOS may block an Internet download.

Windows and Linux run a compiled local service and open the interface in your browser. Keep the launcher running while you work. Neither needs a system Python or Node installation. Read the included README for launch instructions and retained third-party notices. On the first Windows launch, review the retained Microsoft runtime terms and choose Yes only if you accept them. The portable executables are unsigned.

## Try it in three steps

1. Open **Calculate → First calculation** and choose **Ethanol**.
2. Click **Run shape calculation**. Inspect the relaxed 3D structure, signed before/after energy chart, convergence and molecule identity.
3. Click **Download record** to keep the parameters, model version and artifact hashes. Try water or methane next.

With the recorded RDKit 2026.09.1 model and seed 42, ethanol changed from **6.831185 to −1.336852 kcal/mol**. This compares two shapes of the same molecule using the same force field. Raw energies of different molecules cannot rank reactions or experimental stability.

## What was verified

- The compiled Mac interface completed ethanol, water and methane, including 3D and chart rendering, record-save bridge payload, artifact hashes and clearing stale results after changing molecule or project.
- Native frozen Windows and Linux workflow checks ran all three real calculations from a fresh home directory and relocated working directory with Python and Node absent from PATH. Scientific worker checks and relaunch persistence also passed. Interactive GUI checks on Windows and Linux are still needed from community testers.
- Runtime notice and distribution checks passed before the portable archives were published. SHA-256 checksum files and platform QA reports are attached.

## Scientific scope

This is **real molecular mechanics**, not a quantum-chemistry calculation, reaction predictor, experimental validation or proof of a global minimum. ORCA and Q-Chem input preparation remains available for separately installed and licensed engines; real execution of those engines is still unverified. Qwen remains optional and experimental and is not bundled or needed for this activity.

## Source and feedback

The latest reviewed packaging source is **Chem313-1.0.0-preview.6-Source-portable-r3.zip**. The original source ZIP records the Mac build; portable-r2 records the Windows build; portable-r3 adds the Ubuntu package-ownership correction. All use the same first-calculation implementation. GitHub's automatically generated source links refer to the original tag commit; current packaging fixes are on main.

Chem313 is a community research preview. Please report launch problems, unclear instructions and reproducible science issues through [GitHub Issues](https://github.com/jhagir7-arch/chem313/issues), including your OS and the exact error. No private email is published.
