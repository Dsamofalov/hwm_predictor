from __future__ import annotations

import concurrent.futures
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def free_port():
    with socket.socket() as s:s.bind(("127.0.0.1",0));return int(s.getsockname()[1])

def req(base,path,method="GET",payload=None,token=None,timeout=15):
    data=None if payload is None else json.dumps(payload).encode();headers={}
    if data is not None:headers["Content-Type"]="application/json"
    if token:headers["Authorization"]=f"Bearer {token}"
    r=urllib.request.Request(base+path,data=data,method=method,headers=headers)
    try:
        with urllib.request.urlopen(r,timeout=timeout) as x:return x.status,json.loads(x.read().decode())
    except urllib.error.HTTPError as e:return e.code,json.loads(e.read().decode())

def wait_health(base):
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
        port=free_port();base=f"http://127.0.0.1:{port}";env=os.environ.copy()
        env.update(HWM_TOKEN_FILE=str(Path(td)/"token"),HWM_PAIRING_CODE="123456",HWM_ENABLE_DEBUG="1",HWM_SEARCH_SIMS="100000000",HWM_SEARCH_MS="10000",HWM_SEARCH_DEPTH="20",HWM_SEARCH_CANCEL_POLL="1")
        p=subprocess.Popen([exe,str(port)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
        try:
            wait_health(base)
            _,paired=req(base,"/pair","POST",{"code":"123456"});token=paired["token"]
            assert req(base,"/debug/demo-state","POST",{},token)[0]==200
            _,before=req(base,"/status",token=token);assert before["revision"]>=1
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                fut=pool.submit(req,base,"/recommend","POST",None,token,15)
                time.sleep(.15)
                assert req(base,"/debug/demo-state","POST",{},token)[0]==200
                status,result=fut.result(timeout=8)
            _,after=req(base,"/status",token=token)
            assert status==200 and result.get("status")=="stale",result
            assert result.get("cancelled_search") is True,result
            assert result.get("requested_revision")<result.get("current_revision"),result
            assert before["state_hash"]==after["state_hash"],"test must prove revision invalidation even with equal hash"
            assert result.get("elapsed_ms",99999)<5000,result
            print("stale search cooperative cancellation: PASS",result.get("simulations"),result.get("elapsed_ms"))
        finally:
            p.terminate();p.wait(timeout=5)

if __name__=="__main__":main()
