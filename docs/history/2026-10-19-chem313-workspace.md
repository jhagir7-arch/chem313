> Historical design record, not current functionality or a release instruction. See COMMUNITY_HANDOFF.md for present status.

# Chem313 workspace redesign implementation plan

**Goal:** Make a first molecular study understandable without exposing engine-oriented navigation or implying unperformed calculations.
**Architecture:** Four task sections with a native Mac sidebar and equivalent browser sidebar. Keep existing internal workspace IDs for saved commands. Engine selection lives within Calculate. Use shared result presentation and retain exact input, identity and run approval gates.
**Design:** Paper white / charcoal, serif section headings, system sans body, tabular data in monospace, 8 px spacing; one filled primary action per decision, compact persistent molecule context. System/light/dark appearances; editor drawing remains a white scientific canvas.

1. Replace the flat route row with Learn / Molecule / Calculate / Records and opt-in Labs. Add first-launch choices, relevant secondary navigation and engine setting. Verify route mapping and legacy command compatibility.
2. Add native sidebar and toolbar without weakening desktop message origin checks. Compile the Swift shell.
3. Refine guided structure checks, visible feedback, molecule identity card and optional assistant panel. Retain actual identity receipts, learner checks and project-change guards.
4. Present runtime results with molecule context, explicit provenance, energy unit conversions, a primary save and a downloads menu. Do not compare total electronic energies with experimental thermochemistry or manufacture NIST references.
5. Run frontend checks, targeted backend checks and a compiled-app navigation/learning/real RDKit workflow. Verify empty engine states and unavailable Qwen. Record quantum execution as blocked until licensed installation exists.
6. Update the project index and release evidence. Publish only a verified, properly licensed candidate; Windows/Linux native licensing gates remain separate.
