(()=>{
const HWM_D="http://127.0.0.1:38471",hwm$=(id:string)=>document.getElementById(id)!;
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
  const main=hwm$("mainRecommendation"),metrics=hwm$("metrics"),alts=hwm$("alternatives");
  main.className="action";alts.textContent="";
  if(!r||r.status!=="ok"){
    const reason=String(r?.reason??(Array.isArray(r?.warnings)?r.warnings.join(" · "):""));
    if(r?.status==="not_ready" && /semantic/i.test(reason)){
      main.textContent="SEMANTIC STATE UNSAFE — strict recommendation blocked";
    }else if(r?.status==="not_ready"){
      main.textContent="STATE PARTIAL — recommendation intentionally blocked";
    }else{
      main.textContent=`Status: ${r?.status??"unknown"}`;
    }
    main.classList.add(r?.status==="stale"?"warn":"bad");metrics.textContent=reason;return;
  }
  main.textContent=actionText(r.best?.action);main.classList.add("ok");
  const p=Number(r.best?.p_win??0)*100;const ar=Number(r.ability_risk??0)*100;metrics.textContent=`P(win) risk-adjusted: ${p.toFixed(1)}% · ${r.simulations??0} sims · ${Number(r.elapsed_ms??0).toFixed(0)} ms · ability risk ${ar.toFixed(0)}% · state ${r.state_hash??""}${r.semantic_safety_tier?` · safety ${r.semantic_safety_tier}`:""}`;
  if(Array.isArray(r.alternatives)&&r.alternatives.length){
    const title=document.createElement("div");title.className="muted";title.textContent="Alternatives:";alts.appendChild(title);
    for(const x of r.alternatives.slice(0,4)){const d=document.createElement("div");d.textContent=`• ${actionText(x.action)} (${(Number(x.p_win??0)*100).toFixed(1)}%)`;alts.appendChild(d)}
  }
}
async function refresh(){
  try{const h=await fetch(`${HWM_D}/health`).then(r=>r.json());hwm$("health").textContent=`daemon: ${h.status}`;hwm$("health").className="ok";hwm$("status").textContent=JSON.stringify(await fetch(`${HWM_D}/status`).then(r=>r.json()),null,2)}catch(e){hwm$("health").textContent="daemon: offline";hwm$("health").className="bad";hwm$("status").textContent=String(e)}
  try{const x=await chrome.storage.local.get(["hwmLastRecommendation","hwmLastRecommendationAt"]);if(x.hwmLastRecommendation){renderRecommendation(x.hwmLastRecommendation);hwm$("recommendationTime").textContent=x.hwmLastRecommendationAt?new Date(x.hwmLastRecommendationAt).toLocaleTimeString():""}}catch{}
}
async function recommend(){try{const result=await fetch(`${HWM_D}/recommend`,{method:"POST"}).then(r=>r.json());await chrome.storage.local.set({hwmLastRecommendation:result,hwmLastRecommendationAt:Date.now()});renderRecommendation(result)}catch(e){renderRecommendation({status:"offline",error:String(e)})}}
hwm$("recommend").addEventListener("click",recommend);
chrome.runtime.onMessage.addListener((msg:any)=>{if(msg?.type==="recommendation"){renderRecommendation(msg.recommendation);hwm$("recommendationTime").textContent=new Date().toLocaleTimeString()}});
setInterval(refresh,1000);void refresh();
})();
