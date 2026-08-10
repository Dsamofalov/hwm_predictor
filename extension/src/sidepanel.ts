(()=>{
const HWM_D="http://127.0.0.1:38471",TOKEN_KEY="hwmPairingToken",TRACE_KEY="hwmLiveTrace",hwm$=(id:string)=>document.getElementById(id)!;
async function daemonJson(path:string,init:RequestInit={},auth=true):Promise<any>{
  const headers:any={...(init.headers as any||{})};
  if(auth){const s=await chrome.storage.local.get([TOKEN_KEY]);const token=s[TOKEN_KEY];if(!token)return {status:"pairing_required",error:"pairing_required"};headers.Authorization=`Bearer ${token}`}
  const resp=await fetch(`${HWM_D}${path}`,{...init,headers});let data:any;try{data=await resp.json()}catch{data={status:"error",error:`http_${resp.status}`}}
  if(resp.status===401){await chrome.storage.local.remove(TOKEN_KEY);return {...data,status:"pairing_required"}}return data;
}
function actionText(a:any){
  if(!a)return "No action";
  const actor=`stack #${a.actor_uid??"?"}`;
  if(a.type==="MOVE"&&a.destination)return `${actor}: MOVE → (${a.destination.x}, ${a.destination.y}) [protocol coordinates]`;
  if(a.type==="MELEE_ATTACK")return `${actor}: MELEE_ATTACK${a.destination?` from (${a.destination.x}, ${a.destination.y})`:""} → stack #${a.target_uid??"?"}`;
  if(a.type==="RANGED_ATTACK")return `${actor}: RANGED_ATTACK → stack #${a.target_uid??"?"}`;
  if(a.type==="WAIT"||a.type==="DEFEND")return `${actor}: ${a.type}`;
  return `${actor}: ${a.type??"UNKNOWN"}${a.target_uid?` → #${a.target_uid}`:""}`;
}
function renderRecommendation(r:any){
  hwm$("recommendation").textContent=JSON.stringify(r,null,2);
  const main=hwm$("mainRecommendation"),metrics=hwm$("metrics"),alts=hwm$("alternatives");main.className="action";alts.textContent="";
  if(!r||r.status!=="ok"){
    const reason=String(r?.reason??r?.error??(Array.isArray(r?.warnings)?r.warnings.join(" · "):""));
    if(r?.status==="pairing_required"){main.textContent="PAIRING REQUIRED — enter daemon code above"}
    else if(r?.status==="not_ready"&&/semantic/i.test(reason)){main.textContent="SEMANTIC STATE UNSAFE — strict recommendation blocked"}
    else if(r?.status==="not_ready"){main.textContent="STATE PARTIAL — recommendation intentionally blocked"}
    else{main.textContent=`Status: ${r?.status??"unknown"}`}
    main.classList.add(r?.status==="stale"?"warn":"bad");metrics.textContent=reason;return;
  }
  main.textContent=actionText(r.best?.action);main.classList.add("ok");
  const p=Number(r.best?.p_win??0)*100,ar=Number(r.ability_risk??0)*100;metrics.textContent=`P(win) risk-adjusted: ${p.toFixed(1)}% · ${r.simulations??0} sims · ${Number(r.elapsed_ms??0).toFixed(0)} ms · ability risk ${ar.toFixed(0)}% · state ${r.state_hash??""}${r.semantic_safety_tier?` · safety ${r.semantic_safety_tier}`:""}`;
  if(Array.isArray(r.alternatives)&&r.alternatives.length){const title=document.createElement("div");title.className="muted";title.textContent="Alternatives:";alts.appendChild(title);for(const x of r.alternatives.slice(0,4)){const d=document.createElement("div");d.textContent=`• ${actionText(x.action)} (${(Number(x.p_win??0)*100).toFixed(1)}%)`;alts.appendChild(d)}}
}
async function pairedToken(){const x=await chrome.storage.local.get([TOKEN_KEY]);return x[TOKEN_KEY] as string|undefined}
async function guardCurrentRecommendation(r:any){
  if(!r||r.status!=="ok"||!r.state_hash)return r;
  const status=await daemonJson("/status");
  if(status?.state_hash&&status.state_hash!==r.state_hash)return {status:"stale",reason:"recommendation state hash no longer matches current daemon state",requested_state_hash:r.state_hash,current_state_hash:status.state_hash};
  return r;
}
async function updatePairingUi(){const token=await pairedToken();hwm$("pairStatus").textContent=token?"paired":"not paired";hwm$("pairStatus").className=token?"ok":"warn"}
async function refresh(){
  try{const h=await daemonJson("/health",{},false);hwm$("health").textContent=`daemon: ${h.status}`;hwm$("health").className="ok";const token=await pairedToken();if(token){const status=await daemonJson("/status");if(status?.status==="pairing_required"){hwm$("status").textContent="pairing required"}else hwm$("status").textContent=JSON.stringify(status,null,2)}else hwm$("status").textContent="pairing required"}catch(e){hwm$("health").textContent="daemon: offline";hwm$("health").className="bad";hwm$("status").textContent=String(e)}
  await updatePairingUi();
  try{const x=await chrome.storage.local.get(["hwmLastRecommendation","hwmLastRecommendationAt",TRACE_KEY]);if(x.hwmLastRecommendation){const guarded=await guardCurrentRecommendation(x.hwmLastRecommendation);renderRecommendation(guarded);hwm$("recommendationTime").textContent=x.hwmLastRecommendationAt?new Date(x.hwmLastRecommendationAt).toLocaleTimeString():""}const trace=Array.isArray(x[TRACE_KEY])?x[TRACE_KEY]:[];hwm$("liveTrace").textContent=trace.length?JSON.stringify(trace.slice(-30),null,2):"-";const last=trace.at(-1);hwm$("traceSummary").textContent=last?`${new Date(last.at).toLocaleTimeString()} · ${last.stage}${last.revision?` · rev ${last.revision}`:""}${last.stateHash?` · ${String(last.stateHash).slice(0,12)}`:""}`:"No bridge events yet."}catch{}
}
async function pair(){
  const code=(hwm$("pairCode") as HTMLInputElement).value.trim();if(!code){hwm$("pairStatus").textContent="enter pairing code";hwm$("pairStatus").className="warn";return}
  try{const result=await daemonJson("/pair",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({code})},false);if(result?.paired&&result?.token){await chrome.storage.local.set({[TOKEN_KEY]:result.token});(hwm$("pairCode") as HTMLInputElement).value="";hwm$("pairStatus").textContent="paired";hwm$("pairStatus").className="ok";await recommend()}else{hwm$("pairStatus").textContent=result?.error??"pairing failed";hwm$("pairStatus").className="bad"}}catch(e){hwm$("pairStatus").textContent=String(e);hwm$("pairStatus").className="bad"}
}
async function recommend(){try{const raw=await daemonJson("/recommend",{method:"POST"});const result=await guardCurrentRecommendation(raw);await chrome.storage.local.set({hwmLastRecommendation:result,hwmLastRecommendationAt:Date.now()});renderRecommendation(result)}catch(e){renderRecommendation({status:"offline",error:String(e)})}}
hwm$("pair").addEventListener("click",()=>void pair());hwm$("recommend").addEventListener("click",()=>void recommend());hwm$("clearTrace").addEventListener("click",()=>void chrome.storage.local.remove(TRACE_KEY).then(()=>refresh()));
chrome.runtime.onMessage.addListener((msg:any)=>{if(msg?.type==="recommendation"){void guardCurrentRecommendation(msg.recommendation).then(r=>{renderRecommendation(r);hwm$("recommendationTime").textContent=new Date().toLocaleTimeString()})}});
setInterval(refresh,1000);void refresh();
})();
