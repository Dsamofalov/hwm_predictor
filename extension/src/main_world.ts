(()=>{
const HWM_CHANNEL="HWM_SOLVER_CAPTURE_V1";
const HWM_MAX=4*1024*1024;
let hwmSeq=0;

const hwmIsBattleUrl=(u:string)=>{try{return /\/(battle|war|warlog)\.php$/.test(new URL(u,location.href).pathname)}catch{return false}};
const hwmBattleId=(u:string)=>{try{return new URL(u,location.href).searchParams.get("warid")??""}catch{return ""}};
const hwmIsNoopHeartbeat=(u:string,body:string)=>{
  try{
    if(new URL(u,location.href).pathname!=="/battle.php")return false;
  }catch{return false}
  const trimmed=body.trim();
  return trimmed.length>0&&/^\d+$/.test(trimmed);
};

function hwmEmit(source:"fetch"|"xhr",url:string,body:string){
  if(!hwmIsBattleUrl(url)||body.length>HWM_MAX||hwmIsNoopHeartbeat(url,body))return;
  window.postMessage({channel:HWM_CHANNEL,envelope:{
    battleId:hwmBattleId(url)||hwmBattleId(location.href),
    capturedAt:Date.now(),source,
    urlKind:url.includes("battle.php")?"battle_update":"battle_page",
    sequenceHint:++hwmSeq,body,url
  }},"*");
}

const hwmFetch=window.fetch.bind(window);
window.fetch=async (...args:Parameters<typeof fetch>)=>{
  const response=await hwmFetch(...args);
  try{
    const first=args[0];
    const url=typeof first==="string"?first:first instanceof URL?first.toString():first.url;
    if(hwmIsBattleUrl(url))response.clone().text().then(t=>hwmEmit("fetch",url,t)).catch(()=>{});
  }catch{}
  return response;
};

const HwmXHR=window.XMLHttpRequest,hwmOpen=HwmXHR.prototype.open,hwmSend=HwmXHR.prototype.send;
HwmXHR.prototype.open=function(this:XMLHttpRequest,method:string,url:string|URL,async?:boolean,user?:string|null,password?:string|null){
  (this as any).__hwm_url=String(url);
  return (hwmOpen as any).call(this,method,url,async??true,user??null,password??null);
};
HwmXHR.prototype.send=function(this:XMLHttpRequest,body?:Document|XMLHttpRequestBodyInit|null){
  const x=this as any;
  x.addEventListener("load",()=>{try{const u=x.__hwm_url||"";if(hwmIsBattleUrl(u)&&typeof x.responseText==="string")hwmEmit("xhr",u,x.responseText)}catch{}});
  return hwmSend.call(this,body??null);
};
})();
