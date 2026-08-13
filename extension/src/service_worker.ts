(globalThis as any).importScripts("schedule_identity.js");
(()=>{
const HWM_DAEMON="http://127.0.0.1:38471";
const HWM_TOKEN_KEY="hwmPairingToken";
let hwmRecommendTimer:number|undefined;
let hwmRecommendationEpoch=0;
const HWM_TRACE_KEY="hwmLiveTrace";
const HWM_TRACE_MAX=80;
const HWM_WS="ws://127.0.0.1:38471/ws";
let hwmWs:WebSocket|undefined;
let hwmWsReconnectTimer:number|undefined;
const hwmScheduleGuard=hwmCreateScheduleGuard();

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

function hwmReleaseRetryableSchedule(stateKey:string,status:unknown){
  const normalized=String(status??"");
  if(normalized==="pairing_required"||normalized==="offline"||normalized==="error")hwmScheduleGuard.release(stateKey);
}

async function hwmRequestRecommendation(epoch:number,stateKey:string){
  await hwmTrace("plan_requested",{epoch});
  try{
    const recommendation=await hwmDaemonJson("/recommend",{method:"POST"});
    if(epoch!==hwmRecommendationEpoch){await hwmTrace("plan_discarded_epoch",{epoch,currentEpoch:hwmRecommendationEpoch,status:recommendation?.status});return}
    hwmReleaseRetryableSchedule(stateKey,recommendation?.status);
    await hwmTrace("plan_result",{epoch,status:recommendation?.status,stateHash:recommendation?.state_hash??recommendation?.current_state_hash??"",revision:recommendation?.state_revision??recommendation?.current_revision??0,simulations:recommendation?.simulations??0,elapsedMs:recommendation?.elapsed_ms??0});
    await chrome.storage.local.set({hwmLastRecommendation:recommendation,hwmLastRecommendationAt:Date.now()});
    chrome.runtime.sendMessage({type:"recommendation",recommendation}).catch(()=>{});
  }catch(e){
    if(epoch!==hwmRecommendationEpoch){await hwmTrace("plan_error_discarded_epoch",{epoch,currentEpoch:hwmRecommendationEpoch});return}
    hwmScheduleGuard.release(stateKey);
    await hwmTrace("plan_error",{epoch,error:String(e).slice(0,240)});
    await chrome.storage.local.set({hwmLastRecommendation:{status:"offline",error:String(e)},hwmLastRecommendationAt:Date.now()});
  }
}

function hwmScheduleRecommendation(revision=0,stateHash="",battleId=""){
  const stateKey=revision>0?hwmCanonicalScheduleKey(revision,stateHash,battleId):"";
  if(stateKey&&!hwmScheduleGuard.claim(stateKey))return;
  const epoch=++hwmRecommendationEpoch;
  if(hwmRecommendTimer!==undefined)clearTimeout(hwmRecommendTimer);
  hwmRecommendTimer=setTimeout(()=>{hwmRecommendTimer=undefined;void hwmRequestRecommendation(epoch,stateKey)},250) as unknown as number;
}

function hwmResetRecommendationScheduling(){
  hwmScheduleGuard.reset();
  ++hwmRecommendationEpoch;
  if(hwmRecommendTimer!==undefined){clearTimeout(hwmRecommendTimer);hwmRecommendTimer=undefined}
}

async function hwmConnectWebSocket(){
  if(hwmWs&&(hwmWs.readyState===WebSocket.OPEN||hwmWs.readyState===WebSocket.CONNECTING))return;
  const stored=await chrome.storage.local.get([HWM_TOKEN_KEY]);const token=stored[HWM_TOKEN_KEY];if(!token)return;
  try{
    const ws=new WebSocket(HWM_WS,["hwm-v1",`hwm-bearer.${token}`]);hwmWs=ws;
    ws.onopen=()=>{void hwmTrace("ws_connected")};
    ws.onmessage=(event)=>{void (async()=>{try{const msg=JSON.parse(String(event.data));if(msg?.type==="state"&&msg.status){const status=msg.status;await chrome.storage.local.set({hwmLastDaemonStatus:status,hwmLastDaemonStatusAt:Date.now()});await hwmTrace("ws_state",{revision:status.revision??0,stateHash:status.state_hash??"",protocolReady:!!status.protocol_ready,recommendationSafe:!!status.recommendation_safe,sideToAct:status.side_to_act??0});if(status.protocol_ready&&status.recommendation_safe&&status.side_to_act===1&&status.active_entity_uid)hwmScheduleRecommendation(Number(status.revision??0),String(status.state_hash??""),String(status.battle_id??""));}else if(msg?.type==="heartbeat"){await chrome.storage.local.set({hwmLastDaemonStreamAt:Date.now()})}}catch(e){await hwmTrace("ws_message_error",{error:String(e).slice(0,160)})}})()};
    ws.onerror=()=>{void hwmTrace("ws_error")};
    ws.onclose=()=>{if(hwmWs===ws)hwmWs=undefined;void hwmTrace("ws_closed");if(hwmWsReconnectTimer!==undefined)clearTimeout(hwmWsReconnectTimer);hwmWsReconnectTimer=setTimeout(()=>{hwmWsReconnectTimer=undefined;void hwmConnectWebSocket()},1500) as unknown as number};
  }catch(e){await hwmTrace("ws_connect_error",{error:String(e).slice(0,160)})}
}

chrome.storage.onChanged.addListener((changes:any,area:string)=>{if(area==="local"&&changes[HWM_TOKEN_KEY]){hwmResetRecommendationScheduling();if(hwmWs){hwmWs.close();hwmWs=undefined}void hwmConnectWebSocket()}});
void hwmConnectWebSocket();

chrome.runtime.onInstalled.addListener(()=>chrome.sidePanel.setPanelBehavior({openPanelOnActionClick:true}).catch(()=>{}));
chrome.runtime.onMessage.addListener((msg:any,_s:any,sendResponse:any)=>{
  if(msg?.type==="capture"){
    const e=msg.envelope??{};
    void hwmTrace("capture_forwarded",{battleId:String(e.battleId??"").slice(0,80),source:e.source??"",urlKind:e.urlKind??"",sequenceHint:e.sequenceHint??0,bodyBytes:typeof e.body==="string"?e.body.length:0});
    hwmDaemonJson("/capture",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(e)})
      .then(async r=>{await hwmTrace(r?.accepted?"capture_accepted":"capture_rejected",{battleId:String(e.battleId??"").slice(0,80),sequenceHint:e.sequenceHint??0,reason:r?.reason??r?.error??"",revision:r?.revision??0,stateHash:r?.state_hash??"",duplicate:!!r?.duplicate,outOfOrder:!!r?.out_of_order});sendResponse(r);if(r?.accepted&&r?.canonical_state_updated)hwmScheduleRecommendation(Number(r?.revision??0),String(r?.state_hash??""),String(e.battleId??""))})
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
