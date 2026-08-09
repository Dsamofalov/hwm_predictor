(()=>{
const HWM_CAPTURE_CHANNEL="HWM_SOLVER_CAPTURE_V1";
const HWM_PROBE_CHANNEL="HWM_SOLVER_RUNTIME_PROBE_V1";
window.addEventListener("message",e=>{
  if(e.source!==window)return;
  if(e.data?.channel===HWM_CAPTURE_CHANNEL&&e.data?.envelope){
    chrome.runtime.sendMessage({type:"capture",envelope:e.data.envelope}).catch(()=>{});
  }else if(e.data?.channel===HWM_PROBE_CHANNEL&&e.data?.probe){
    chrome.runtime.sendMessage({type:"runtime_probe",probe:e.data.probe}).catch(()=>{});
  }
});
})();
