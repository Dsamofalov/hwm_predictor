(()=>{
const HWM_DAEMON="http://127.0.0.1:38471";
const HWM_TOKEN_KEY="hwmPairingToken";
let hwmRecommendTimer:number|undefined;
let hwmRecommendationEpoch=0;
const HWM_TRACE_KEY="hwmLiveTrace";
const HWM_TRACE_MAX=80;

type HwmTraceEvent={at:number;stage:string;[key:string]:unknown};
async function hwmTrace(stage:string,details:Record<string,unknown>={}){
  try{
    const stored=await chrome.storage.local.get([HWM_TRACE_KEY]);
    const trace:Array<HwmTraceEvent>=Array.isArray(stored[HWM_TRACE_KEY])?stored[HWM_TRACE_KEY].slice(-HWM_TRACE_MAX+1):[];
    trace.push({at:Date.now(),stage,...details});
    await chrome.storage.local.set({[HWM_TRACE_KEY]:trace});
  }catch{}
}

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
  await hwmTrace("plan_requested",{epoch});
  try{
    const recommendation=await hwmDaemonJson("/recommend",{method:"POST"});
    if(epoch!==hwmRecommendationEpoch){await hwmTrace("plan_discarded_epoch",{epoch,currentEpoch:hwmRecommendationEpoch,status:recommendation?.status});return}
    await hwmTrace("plan_result",{epoch,status:recommendation?.status,stateHash:recommendation?.state_hash??recommendation?.current_state_hash??"",revision:recommendation?.state_revision??recommendation?.current_revision??0,simulations:recommendation?.simulations??0,elapsedMs:recommendation?.elapsed_ms??0});
    await chrome.storage.local.set({hwmLastRecommendation:recommendation,hwmLastRecommendationAt:Date.now()});
    chrome.runtime.sendMessage({type:"recommendation",recommendation}).catch(()=>{});
  }catch(e){
    if(epoch!==hwmRecommendationEpoch){await hwmTrace("plan_error_discarded_epoch",{epoch,currentEpoch:hwmRecommendationEpoch});return}
    await hwmTrace("plan_error",{epoch,error:String(e).slice(0,240)});
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
    const e=msg.envelope??{};
    void hwmTrace("capture_forwarded",{battleId:String(e.battleId??"").slice(0,80),source:e.source??"",urlKind:e.urlKind??"",sequenceHint:e.sequenceHint??0,bodyBytes:typeof e.body==="string"?e.body.length:0});
    hwmDaemonJson("/capture",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(e)})
      .then(async r=>{await hwmTrace(r?.accepted?"capture_accepted":"capture_rejected",{battleId:String(e.battleId??"").slice(0,80),sequenceHint:e.sequenceHint??0,reason:r?.reason??r?.error??"",revision:r?.revision??0,stateHash:r?.state_hash??"",duplicate:!!r?.duplicate,outOfOrder:!!r?.out_of_order});sendResponse(r);if(r?.accepted)hwmScheduleRecommendation()})
      .catch(async e=>{await hwmTrace("capture_error",{error:String(e).slice(0,240)});sendResponse({accepted:false,error:String(e)})});
    return true;
  }
  if(msg?.type==="runtime_probe"){
    hwmDaemonJson("/runtime-probe",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(msg.probe)})
      .then(async r=>{await hwmTrace("runtime_probe_result",{accepted:!!r?.accepted,error:r?.error??""});await chrome.storage.local.set({hwmLastRuntimeProbe:r,hwmLastRuntimeProbeAt:Date.now()});sendResponse(r)})
      .catch(e=>sendResponse({accepted:false,error:String(e)}));
    return true;
  }
});
})();
