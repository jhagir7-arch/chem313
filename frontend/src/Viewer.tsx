import React,{useEffect,useRef,useState} from 'react';

export default function Viewer({data,format='sdf'}:{data:string|null;format?:string}){
  const host=useRef<HTMLDivElement>(null);const [error,setError]=useState('');
  useEffect(()=>{let alive=true;let viewer:any;
    if(!data||!host.current)return;
    import('3dmol/build/3Dmol.js').then(mod=>{
      if(!alive||!host.current)return;
      const lib=(mod as any).default??mod;
      viewer=lib.createViewer(host.current,{backgroundColor:'#ffffff',antialias:true});
      viewer.addModel(data,format);viewer.setStyle({},{stick:{radius:.16},sphere:{scale:.28}});viewer.zoomTo();viewer.render();setError('');
    }).catch(e=>setError(String(e)));
    return()=>{alive=false;viewer?.clear();if(host.current)host.current.replaceChildren();};
  },[data,format]);
  return <div className="viewer-wrap"><div className="viewer" ref={host}/>{!data&&<div className="viewer-empty">{format==='xyz'?'No Cartesian geometry was printed in this file.':'Generate a conformer to explore the structure in 3D.'}</div>}{error&&<p role="alert">3D view unavailable: {error}</p>}<span className="viewer-hint">Drag to rotate · Scroll to zoom</span></div>;
}
