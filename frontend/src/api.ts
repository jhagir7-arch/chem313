export type Artifact = {relative_path:string; sha256:string; bytes:number};
export type Reply = {status:string; action:string; result:any; artifacts:Artifact[]; preview_token?:string; request_sha256?:string; warning?:string};
let token:Promise<string>|null=null;
async function session(){
  if(!token) token=fetch('/api/session').then(async r=>{if(!r.ok)throw Error('The local engine is unavailable');return (await r.json()).session_token as string;}).catch(e=>{token=null;throw e;});
  return token;
}
export async function request(path:string,body?:unknown):Promise<any>{
  const response=await fetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-HypothesisLab-Session':await session()},body:body?JSON.stringify(body):undefined});
  if(!response.ok){const error=await response.json().catch(()=>({}));throw Error(typeof error.detail==='string'?error.detail:`Request failed (${response.status})`);}
  return response.json();
}
export const execute=async(action:string,params:Record<string,unknown>,project:string)=>request('/api/execute',{action,params,project,approved:true}) as Promise<Reply>;
export async function artifactBytes(a:Artifact){
  const [project,group,file]=a.relative_path.split('/');
  const r=await fetch(`/api/projects/${encodeURIComponent(project)}/artifact/${group}/${file}`,{headers:{'X-HypothesisLab-Session':await session()}});
  if(!r.ok)throw Error(`Cannot read saved file (${r.status})`);
  return new Uint8Array(await r.arrayBuffer());
}
export function saveBytes(bytes:Uint8Array,name:string,mime='application/octet-stream'){
  const desktop=(window as any).webkit?.messageHandlers?.desktop;
  if(desktop){let binary='';for(const byte of bytes)binary+=String.fromCharCode(byte);desktop.postMessage({action:'save',name,base64:btoa(binary)});return;}
  const blob=new Blob([bytes as BlobPart],{type:mime});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1500);
}
export function saveText(text:string,name:string,mime='text/plain'){saveBytes(new TextEncoder().encode(text),name,mime);}
