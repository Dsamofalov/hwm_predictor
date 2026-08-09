(()=>{
const HWM_CHANNEL="HWM_SOLVER_CAPTURE_V1";
const HWM_PROBE_CHANNEL="HWM_SOLVER_RUNTIME_PROBE_V1";
const HWM_MAX=4*1024*1024;
let hwmSeq=0;
let hwmProbeSeq=0;

const hwmIsBattleUrl=(u:string)=>{try{return /\/(battle|war|warlog)\.php$/.test(new URL(u,location.href).pathname)}catch{return false}};
const hwmBattleId=(u:string)=>{try{return new URL(u,location.href).searchParams.get("warid")??""}catch{return ""}};

function hwmEmit(source:"fetch"|"xhr",url:string,body:string){
  if(!hwmIsBattleUrl(url)||body.length>HWM_MAX)return;
  window.postMessage({channel:HWM_CHANNEL,envelope:{
    battleId:hwmBattleId(url)||hwmBattleId(location.href),
    capturedAt:Date.now(),source,
    urlKind:url.includes("battle.php")?"battle_update":"battle_page",
    sequenceHint:++hwmSeq,body,url
  }},"*");
}

const HWM_INTERESTING=/battle|war|unit|creature|stack|turn|initiative|atb|combat|fight|hero|spell|effect|buff|debuff|arena|field|pixi|game/i;
const HWM_SENSITIVE=/cookie|token|auth|session|password|passwd|secret|credential|storage|localstorage|sessionstorage|indexeddb/i;

type HwmFieldShape={name:string;type:string;ctor?:string;keys?:string[];accessor?:boolean};
type HwmObjectShape={name:string;type:string;ctor?:string;ownKeyCount?:number;arrayLength?:number;fields?:HwmFieldShape[]};

function hwmCtor(v:unknown):string|undefined{
  if(v===null||typeof v!=="object"&&typeof v!=="function")return undefined;
  try{return (v as any).constructor?.name?.slice(0,80)}catch{return undefined}
}

function hwmObjectFieldNames(v:unknown,limit=100):string[]{
  if(v===null||(typeof v!=="object"&&typeof v!=="function"))return [];
  try{return Object.getOwnPropertyNames(v).filter(k=>!HWM_SENSITIVE.test(k)).slice(0,limit)}catch{return []}
}

function hwmLooksInteresting(name:string,v:unknown):boolean{
  if(HWM_SENSITIVE.test(name))return false;
  if(HWM_INTERESTING.test(name))return true;
  if(v===null||(typeof v!=="object"&&typeof v!=="function"))return false;
  const keys=hwmObjectFieldNames(v,80);
  return keys.some(k=>HWM_INTERESTING.test(k));
}

function hwmShape(name:string,v:unknown):HwmObjectShape{
  const type=v===null?"null":typeof v;
  const out:HwmObjectShape={name,type};
  const ctor=hwmCtor(v);if(ctor)out.ctor=ctor;
  if(v===null||(type!=="object"&&type!=="function"))return out;
  let descs:Record<string,PropertyDescriptor>={};
  try{descs=Object.getOwnPropertyDescriptors(v)}catch{return out}
  const names=Object.keys(descs).filter(k=>!HWM_SENSITIVE.test(k));
  out.ownKeyCount=names.length;
  if(Array.isArray(v))out.arrayLength=v.length;
  const preferred=[...names.filter(k=>HWM_INTERESTING.test(k)),...names.filter(k=>!HWM_INTERESTING.test(k))].slice(0,80);
  out.fields=preferred.map((key):HwmFieldShape=>{
    const d=descs[key];
    if(!d||!("value" in d))return {name:key,type:"accessor",accessor:true};
    const x=d.value;
    const field:HwmFieldShape={name:key,type:x===null?"null":typeof x};
    const c=hwmCtor(x);if(c)field.ctor=c;
    if(x!==null&&(typeof x==="object"||typeof x==="function"))field.keys=hwmObjectFieldNames(x,24);
    return field;
  });
  return out;
}

function hwmEmitRuntimeProbe(){
  // Structure only: no primitive values, cookies, storage contents, or getter invocation.
  const battleId=hwmBattleId(location.href);
  if(!battleId&&!hwmIsBattleUrl(location.href))return;
  const candidates:HwmObjectShape[]=[];
  let names:string[]=[];
  try{names=Object.getOwnPropertyNames(window)}catch{return}
  for(const name of names){
    if(candidates.length>=100)break;
    if(HWM_SENSITIVE.test(name))continue;
    let d:PropertyDescriptor|undefined;
    try{d=Object.getOwnPropertyDescriptor(window,name)}catch{continue}
    if(!d||!("value" in d))continue; // do not execute global getters
    const v=d.value;
    if(!hwmLooksInteresting(name,v))continue;
    candidates.push(hwmShape(name,v));
  }
  window.postMessage({channel:HWM_PROBE_CHANNEL,probe:{
    schema:"hwm-runtime-structure-v1",
    battleId,
    capturedAt:Date.now(),
    sequenceHint:++hwmProbeSeq,
    pageKind:hwmIsBattleUrl(location.href)?"battle":"other",
    candidateCount:candidates.length,
    candidates
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

setTimeout(hwmEmitRuntimeProbe,1800);
setInterval(hwmEmitRuntimeProbe,10000);
})();
