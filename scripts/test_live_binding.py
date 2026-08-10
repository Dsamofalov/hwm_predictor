from __future__ import annotations

import json,os,socket,subprocess,sys,tempfile,time,urllib.error,urllib.request
from pathlib import Path

def free_port():
    with socket.socket() as s:s.bind(("127.0.0.1",0));return int(s.getsockname()[1])
def req(base,path,method="GET",payload=None,token=None,timeout=8):
    data=None if payload is None else json.dumps(payload).encode();headers={}
    if data is not None:headers["Content-Type"]="application/json"
    if token:headers["Authorization"]=f"Bearer {token}"
    r=urllib.request.Request(base+path,data=data,method=method,headers=headers)
    try:
        with urllib.request.urlopen(r,timeout=timeout) as x:return x.status,json.loads(x.read().decode())
    except urllib.error.HTTPError as e:return e.code,json.loads(e.read().decode())
def wait(base):
    end=time.time()+8
    while time.time()<end:
        try:
            if req(base,"/health",timeout=1)[0]==200:return
        except Exception:pass
        time.sleep(.05)
    raise AssertionError("daemon not healthy")
def main():
    exe=sys.argv[1] if len(sys.argv)>1 else "build/debug/solver-daemon"
    with tempfile.TemporaryDirectory() as td:
        port=free_port();base=f"http://127.0.0.1:{port}";env=os.environ.copy();env.update(HWM_TOKEN_FILE=str(Path(td)/"token"),HWM_PAIRING_CODE="123456",HWM_ENABLE_DEBUG="1",HWM_SEARCH_SIMS="64",HWM_SEARCH_MS="1000",HWM_SEARCH_DEPTH="4")
        p=subprocess.Popen([exe,str(port)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
        try:
            wait(base);_,paired=req(base,"/pair","POST",{"code":"123456"});token=paired["token"]
            assert req(base,"/debug/demo-state","POST",{},token)[0]==200
            _,status=req(base,"/status",token=token);assert status["revision"]>=1 and status["state_hash"]
            code,rec=req(base,"/recommend","POST",None,token);assert code==200,rec
            assert rec.get("status")=="ok",rec
            assert rec.get("state_hash")==status["state_hash"],(rec,status)
            assert rec.get("state_revision")==status["revision"],(rec,status)
            assert rec.get("battle_id")=="demo",rec
            print("live recommendation binding contract: PASS",rec["state_revision"],rec["state_hash"])
        finally:p.terminate();p.wait(timeout=5)
if __name__=="__main__":main()
