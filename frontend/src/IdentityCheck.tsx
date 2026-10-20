import React from 'react';

type Identity={status?:string;expected_inchikey?:string|null;observed_inchikey?:string|null;scope?:string;detail?:string};

export default function IdentityCheck({identity,scope}:{identity:Identity;scope?:string}){
 const matched=identity.status==='match';
 const status=matched?'✓ Identity verified (InChI)':identity.status==='mismatch'?'Identity mismatch — do not export this preparation':'Identity verification unavailable';
 const detail=matched?'The server matched the coordinate-derived identifier to the selected lesson molecule.':identity.detail??'A verified coordinate-derived identity receipt is not available for this preparation.';
 return <section className={'qchem-identity '+(matched?'verified':'unverified')} aria-label="Coordinate identity check">
  <strong>{status}</strong><span>{detail}</span>
  <details><summary>Identity receipt details</summary>{matched&&<dl className="qchem-summary"><div><dt>Expected InChIKey</dt><dd><code>{identity.expected_inchikey??'Unavailable'}</code></dd></div><div><dt>Coordinates InChIKey</dt><dd><code>{identity.observed_inchikey??'Unavailable'}</code></dd></div></dl>}<p className="quiet-note">{scope??identity.scope??'A verified match checks structure identity from the supplied coordinates. It does not prove geometry quality, state, method suitability, or calculation results.'}</p></details>
 </section>;
}
