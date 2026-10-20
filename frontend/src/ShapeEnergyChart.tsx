import React from 'react';

type Shape={seed:number;relativeEnergy:number;force_field:string;energy_unit:string;editorSmiles:string};
/** The caller supplies the common-model ranking from rankStartingShapes. */
export default function ShapeEnergyChart({shapes,selectedSeed,onSelect,disabled}:{shapes:Shape[];selectedSeed?:number;onSelect:(shape:any)=>void;disabled:boolean}){
 if(!shapes.length)return null;
 const first=shapes[0];
 if(shapes.some(s=>!Number.isFinite(s.relativeEnergy)||s.relativeEnergy<0||s.force_field!==first.force_field||s.editorSmiles!==first.editorSmiles||s.energy_unit!=='kcal/mol'))return <p role="alert">These energies cannot be plotted together: use the same molecule, force field and units.</p>;
 const maximum=Math.max(...shapes.map(s=>s.relativeEnergy));
 return <figure className="shape-energy-chart"><figcaption><strong>Which sampled shape has lower energy?</strong><span>Relative force-field energy · kcal/mol · {first.force_field}</span></figcaption><p>Longer bars mean higher energy. Zero is the lowest sample found; it is not an absolute zero of molecular energy.</p><div className="energy-bars">{shapes.map((shape,index)=><button type="button" key={shape.seed} aria-pressed={shape.seed===selectedSeed} disabled={disabled} onClick={()=>onSelect(shape)} aria-label={`Inspect sample ${index+1}, ${shape.relativeEnergy.toFixed(3)} kilocalories per mole above the lowest sample`}><span>Sample {index+1}</span><span className="energy-bar-track"><span style={{width:`${maximum>0?shape.relativeEnergy/maximum*100:0}%`}}/></span><strong>{shape.relativeEnergy.toFixed(3)}</strong></button>)}</div>{maximum<0.001&&<p className="quiet-note">All samples reached almost the same energy. Sampling repeatedly can find the same minimum; try butane to explore more starting shapes.</p>}<p className="quiet-note">Compare samples of this molecule only. This plot does not establish a reaction, quantum accuracy, or a global minimum. Exact values are in the table below.</p></figure>;
}
