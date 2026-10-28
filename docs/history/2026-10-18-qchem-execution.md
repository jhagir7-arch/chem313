> Historical implementation plan; real licensed-engine validation was not established.

# Q-Chem execution and beginner results

User goal: select a teaching molecule, launch real Q-Chem locally, and understand the recorded output with Qwen help in the compiled app.

Architecture: authenticated local runtime launches the separately licensed QC/bin/qchem with one thread and isolated scratch. Server renders the fixed neutral-singlet HF/def2-SVP input. The lesson gains a run/results step; Qwen classifies questions and checked explanations cite authoritative persisted job results, never client-supplied energies.

Constraints: no engine substitution, fabricated production results, license bypass, purchase or external submission. Existing dirty work and user data preserved. Missing licensed engine is an explicit incomplete verification boundary.

- [x] Backend: configure installation, approved launch, status/cancel, bounded output/time, durable jobs/artifacts and interrupted recovery. Test success, license/SCF failure, truncation, cancellation, invalid coordinates and auth.
- [x] UI: fifth step with connection status, exact-input run review, recovery, readable status/results, raw files and result understanding check. Preserve keyboard/responsive monochrome lesson.
- [x] Qwen: explain server-fetched results with model provenance; reject foreign projects and unsupported claims; no invented energies.
- [x] Package: rebuild installed native application and notices, verify signature and hashes. Test compiled missing-engine behavior and clearly labelled simulated execution separately. Real calculation only after licensed installation is available.

Review focus: stale geometry versus stored job; process cancellation across restart; return-zero output without convergence; unavailable model; connected installation without working license.

