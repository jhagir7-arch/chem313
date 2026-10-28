// 3Dmol ball-and-stick viewer, loaded lazily. Keyboard: arrows rotate, +/− zoom, 0 fits.
import {useEffect, useRef} from 'react';

type Viewer = {
  addModel: (data: string, format: string) => void; setStyle: (sel: object, style: object) => void; zoomTo: () => void; render: () => void;
  clear: () => void; rotate: (angle: number, axis: string) => void; zoom: (factor: number) => void; setBackgroundColor: (c: string) => void; resize: () => void;
};

export default function Viewer3D({sdf}: {sdf: string}) {
  const host = useRef<HTMLDivElement>(null);
  const viewer = useRef<Viewer | null>(null);

  useEffect(() => {
    let disposed = false;
    const el = host.current;
    if (!el) return;
    import('3dmol/build/3Dmol.js').then((mod: any) => {
      if (disposed || !host.current) return;
      const $3Dmol = mod.default ?? mod;
      const bg = getComputedStyle(document.documentElement).getPropertyValue('--bg-viewport').trim() || '#121417';
      const v: Viewer = $3Dmol.createViewer(host.current, {backgroundColor: bg, antialias: true});
      v.addModel(sdf, 'sdf');
      v.setStyle({}, {stick: {radius: 0.16}, sphere: {scale: 0.28}});
      v.zoomTo();
      v.render();
      viewer.current = v;
    });
    const onKey = (e: KeyboardEvent) => {
      const v = viewer.current;
      if (!v || e.metaKey || e.ctrlKey || document.activeElement !== el) return;
      if (e.key === 'ArrowLeft') v.rotate(-10, 'y'); else if (e.key === 'ArrowRight') v.rotate(10, 'y');
      else if (e.key === 'ArrowUp') v.rotate(-10, 'x'); else if (e.key === 'ArrowDown') v.rotate(10, 'x');
      else if (e.key === '+' || e.key === '=') v.zoom(1.2); else if (e.key === '-') v.zoom(1 / 1.2);
      else if (e.key === '0') v.zoomTo(); else return;
      v.render();
      e.preventDefault();
    };
    el.addEventListener('keydown', onKey);
    const ro = new ResizeObserver(() => { viewer.current?.resize(); viewer.current?.render(); });
    ro.observe(el);
    return () => {
      disposed = true;
      ro.disconnect();
      el.removeEventListener('keydown', onKey);
      viewer.current?.clear();
      viewer.current = null;
      el.replaceChildren();
    };
  }, [sdf]);

  return (
    <div className="viewport" style={{display: 'block', padding: 0}}>
      <div ref={host} tabIndex={0} aria-label="3D model; arrow keys rotate, plus and minus zoom, 0 fits" style={{position: 'absolute', inset: 0, outline: 'none'}} />
      <span className="corner r mono">drag to rotate · ←→↑↓ · +/− · 0 fit · 3Dmol</span>
    </div>
  );
}
