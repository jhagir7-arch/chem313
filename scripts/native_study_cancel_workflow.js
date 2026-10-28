const wait=async(fn,label)=>{const end=Date.now()+120000;while(Date.now()<end){const v=await fn();if(v)return v;await new Promise(r=>setTimeout(r,10));}throw Error('Timed out '+label)};
const button=name=>[...document.querySelectorAll('button')].find(x=>x.getClientRects().length&&x.textContent.trim()===name);
try{
 const q=await wait(()=>document.getElementById('study-question'),'question');
 Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(q,'Compare eight shapes of caffeine');q.dispatchEvent(new Event('input',{bubbles:true}));await new Promise(r=>requestAnimationFrame(r));
 button('Prepare study').click();await wait(()=>button('Run study')&&!button('Run study').disabled,'Qwen plan');
 if(!document.querySelector('.study-identity img'))throw Error('No checked 2D plan structure');
 button('Run study').click();
 const cancel=await wait(()=>button('Cancel run'),'Cancel control');
 if(!q.disabled)throw Error('Question can hide an active run');
 cancel.click();
 await wait(()=>document.querySelector('.study-live').textContent.includes('cancelled')||document.querySelector('.study-live').textContent.includes('complete'),'finished cancellation');
 const text=document.querySelector('.study-live').textContent;
 const rows=document.querySelectorAll('.study-table-wrap tbody tr').length;
 if(!rows)throw Error('No retained completed result');
 if(!text.includes('cancelled')||rows>=8)throw Error('Run completed before partial cancellation was observed: '+text+' rows '+rows);
 return JSON.stringify({status:'PASS',host:'compiled AppKit/WKWebView',checks:['Real Qwen caffeine plan displays checked 2D graph','Question stays disabled during active study','Cancel stops further real RDKit scheduling and retains completed samples'],completed:rows,requested:8});
}catch(error){return JSON.stringify({status:'FAIL',error:String(error),body:document.body.innerText.slice(-6000)});}
