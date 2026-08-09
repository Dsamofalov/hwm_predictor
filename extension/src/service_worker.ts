(()=>{
const HWM_DAEMON="http://127.0.0.1:38471";
let hwmRecommendTimer:number|undefined;

async function hwmRequestRecommendation(){
  try{
    const recommendation=await fetch(`${HWM_DAEMON}/recommend`,{method:"POST"}).then(r=>r.json());
    await chrome.storage.local.set({hwmLastRecommendation:recommendation,hwmLastRecommendationAt:Date.now()});
    chrome.runtime.sendMessage({type:"recommendation",recommendation}).catch(()=>{});
  }catch(e){
    await chrome.storage.local.set({hwmLastRecommendation:{status:"offline",error:String(e)},hwmLastRecommendationAt:Date.now()});
  }
}

function hwmScheduleRecommendation(){
  if(hwmRecommendTimer!==undefined)clearTimeout(hwmRecommendTimer);
  hwmRecommendTimer=setTimeout(()=>{hwmRecommendTimer=undefined;void hwmRequestRecommendation()},250) as unknown as number;
}

chrome.runtime.onInstalled.addListener(()=>chrome.sidePanel.setPanelBehavior({openPanelOnActionClick:true}).catch(()=>{}));
chrome.runtime.onMessage.addListener((msg:any,_s:any,sendResponse:any)=>{
  if(msg?.type==="capture"){
    fetch(`${HWM_DAEMON}/capture`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(msg.envelope)})
      .then(r=>r.json())
      .then(r=>{sendResponse(r);if(r?.accepted)hwmScheduleRecommendation()})
      .catch(e=>sendResponse({accepted:false,error:String(e)}));
    return true;
  }
  if(msg?.type==="runtime_probe"){
    fetch(`${HWM_DAEMON}/runtime-probe`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(msg.probe)})
      .then(r=>r.json())
      .then(async r=>{await chrome.storage.local.set({hwmLastRuntimeProbe:r,hwmLastRuntimeProbeAt:Date.now()});sendResponse(r)})
      .catch(e=>sendResponse({accepted:false,error:String(e)}));
    return true;
  }
});
})();
