# Source origin and license scope

OpenChem combines project-generated OpenChem/HypothesisLab handoff code with the local Fieldnote ORCA reader and subsequent desktop, workflow and integration development. These were developed for this project using coding agents. The retained handoff rights records describe independent interface-level implementation and explicitly exclude proprietary code, third-party source repositories, binaries and model files. They deferred the project-wide license until the maintainer selected it; the maintainer has now requested public release and license completion.

This release applies Apache-2.0 to OpenChem-originated source and documentation. It does not assert ownership of upstream libraries or extend the grant to external files. The source review found no affirmative indication that proprietary application source was transplanted into the included implementation. This is a documented, bounded review, not a guarantee of every generated line's originality.

The public export deliberately excludes original handoff archives, private receipts and development history. It also excludes six third-party cclib-data ORCA outputs because their redistribution license was not established, and excludes model weights from the source ZIP. The historical preview.2 model edition includes the licensed upstream base model; the private adapter and training data remain excluded because their distribution lineage was not completed. The original fixture URL/hash manifest remains for provenance; tests explicitly skip when the excluded files are absent.

The historical standalone preview.2 app bundles the runtimes and Qwen base model described
in THIRD_PARTY_NOTICES.md, with artifact-local notices and ownership manifests.
The corresponding source ZIP contains application/build code and excludes those
installed binaries and weights. ORCA and Avogadro remain external applications.

Chem313 preview.3 is the renamed standalone core. It excludes model weights and optional worker environments; the earlier OpenChem names in provenance records identify project history and are retained intentionally.

If you identify material that needs attribution or correction, open a repository issue identifying the file and the original source. Contributions must include their source and applicable license. Do not submit proprietary code, credentials, researcher data, or third-party calculation files without permission.
