import React,{useEffect,useRef,useState} from 'react';

export default function Viewer({data,format='sdf'}:{data:string|null;format?:string}){
  const host=useRef<HTMLDivElement>(null),control=useRef<any>(null);const [error,setError]=useState(''),[ready,setReady]=useState(false);
  useEffect(()=>{let alive=true;let viewer:any;setReady(false);
    if(!data||!host.current)return;
    import('3dmol/build/3Dmol.js').then(mod=>{
      if(!alive||!host.current)return;
      const lib=(mod as any).default??mod;
      viewer=lib.createViewer(host.current,{backgroundColor:'#ffffff',antialias:true});control.current=viewer;
      viewer.addModel(data,format);viewer.setStyle({},{stick:{radius:.16},sphere:{scale:.28}});viewer.zoomTo();viewer.render();setError('');setReady(true);
    }).catch(e=>{if(alive)setError(String(e));});
    return()=>{alive=false;control.current=null;viewer?.clear();if(host.current)host.current.replaceChildren();};
  },[data,format]);
  function move(action:string){const v=control.current;if(!v)return;if(action==='left')v.rotate(-15,'y');if(action==='right')v.rotate(15,'y');if(action==='up')v.rotate(-15,'x');if(action==='down')v.rotate(15,'x');if(action==='in')v.zoom(1.2);if(action==='out')v.zoom(1/1.2);if(action==='reset')v.zoomTo();v.render();}
  return <div className="viewer-wrap"><div className="viewer" ref={host}/>{!data&&<div className="viewer-empty">{format==='xyz'?'No Cartesian geometry was printed in this file.':'Generate a starting shape to explore the structure in 3D.'}</div>}{error&&<p role="alert">3D view unavailable: {error}</p>}{data&&<div className="viewer-controls" aria-label="3D model controls">{[['left','↶','Rotate left'],['right','↷','Rotate right'],['up','↑','Rotate up'],['down','↓','Rotate down'],['in','+','Zoom in'],['out','−','Zoom out'],['reset','Fit','Fit model']].map(([action,label,title])=><button type="button" key={action} aria-label={title} title={title} disabled={!ready} onClick={()=>move(action)}>{label}</button>)}</div>}<span className="viewer-hint">Drag to rotate · or use the buttons below</span></div>;
}
