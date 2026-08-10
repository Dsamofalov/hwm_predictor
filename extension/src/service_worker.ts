(()=>{
const HWM_DAEMON="http://127.0.0.1:38471";
const HWM_TOKEN_KEY="hwmPairingToken";
let hwmRecommendTimer:number|undefined;
let hwmRecommendationEpoch=0;

async function hwmDaemonJson(path:string,init:RequestInit={},auth=true):Promise<any>{
  const headers:any={...(init.headers as any||{})};
  if(auth){
    const stored=await chrome.storage.local.get([HWM_TOKEN_KEY]);
    const token=stored[HWM_TOKEN_KEY];
    if(!token)return {status:"pairing_required",accepted:false,error:"pairing_required"};
    headers.Authorization=`Bearer ${token}`;
  }
  const response=await fetch(`${HWM_DAEMON}${path}`,{...init,headers});
  let data:any;try{data=await response.json()}catch{data={status:"error",error:`http_${response.status}`}}
  if(response.status===401){await chrome.storage.local.remove(HWM_TOKEN_KEY);return {...data,status:"pairing_required",accepted:false}}
  return data;
}

async function hwmRequestRecommendation(epoch:number){
  try{
    const recommendation=await hwmDaemonJson("/recommend",{method:"POST"});
    if(epoch!==hwmRecommendationEpoch)return;
    await chrome.storage.local.set({hwmLastRecommendation:recommendation,hwmLastRecommendationAt:Date.now()});
    chrome.runtime.sendMessage({type:"recommendation",recommendation}).catch(()=>{});
  }catch(e){
    if(epoch!==hwmRecommendationEpoch)return;
    await chrome.storage.local.set({hwmLastRecommendation:{status:"offline",error:String(e)},hwmLastRecommendationAt:Date.now()});
  }
}

function hwmScheduleRecommendation(){
  const epoch=++hwmRecommendationEpoch;
  if(hwmRecommendTimer!==undefined)clearTimeout(hwmRecommendTimer);
  hwmRecommendTimer=setTimeout(()=>{hwmRecommendTimer=undefined;void hwmRequestRecommendation(epoch)},250) as unknown as number;
}

chrome.runtime.onInstalled.addListener(()=>chrome.sidePanel.setPanelBehavior({openPanelOnActionClick:true}).catch(()=>{}));
chrome.runtime.onMessage.addListener((msg:any,_s:any,sendResponse:any)=>{
  if(msg?.type==="capture"){
    hwmDaemonJson("/capture",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(msg.envelope)})
      .then(r=>{sendResponse(r);if(r?.accepted)hwmScheduleRecommendation()})
      .catch(e=>sendResponse({accepted:false,error:String(e)}));
    return true;
  }
  if(msg?.type==="runtime_probe"){
    hwmDaemonJson("/runtime-probe",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(msg.probe)})
      .then(async r=>{await chrome.storage.local.set({hwmLastRuntimeProbe:r,hwmLastRuntimeProbeAt:Date.now()});sendResponse(r)})
      .catch(e=>sendResponse({accepted:false,error:String(e)}));
    return true;
  }
});
})();
