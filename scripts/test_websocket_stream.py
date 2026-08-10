from __future__ import annotations
import base64,hashlib,json,os,socket,subprocess,sys,tempfile,time,urllib.error,urllib.request
from pathlib import Path
GUID="258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
def free_port():
    with socket.socket() as s:s.bind(("127.0.0.1",0));return int(s.getsockname()[1])
def req(base,path,method="GET",payload=None,token=None,timeout=5):
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
def recv_until(s,marker):
    data=b""
    while marker not in data:data+=s.recv(4096)
    return data
def recv_frame(s):
    h=s.recv(2);assert len(h)==2 and (h[0]&0x0f)==1,h
    n=h[1]&0x7f
    if n==126:n=int.from_bytes(s.recv(2),"big")
    elif n==127:n=int.from_bytes(s.recv(8),"big")
    assert not (h[1]&0x80)
    data=b""
    while len(data)<n:data+=s.recv(n-len(data))
    return json.loads(data.decode())
def connect_ws(port,token):
    s=socket.create_connection(("127.0.0.1",port),timeout=3);s.settimeout(4);key=base64.b64encode(os.urandom(16)).decode()
    request=(f"GET /ws HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Protocol: hwm-v1, hwm-bearer.{token}\r\nOrigin: chrome-extension://integration-test\r\n\r\n").encode();s.sendall(request);headers=recv_until(s,b"\r\n\r\n").decode();assert "101 Switching Protocols" in headers,headers
    expected=base64.b64encode(hashlib.sha1((key+GUID).encode()).digest()).decode();assert f"Sec-WebSocket-Accept: {expected}" in headers,headers;assert "Sec-WebSocket-Protocol: hwm-v1" in headers;return s
def main():
    exe=sys.argv[1] if len(sys.argv)>1 else "build/debug/solver-daemon"
    with tempfile.TemporaryDirectory() as td:
        port=free_port();base=f"http://127.0.0.1:{port}";env=os.environ.copy();env.update(HWM_TOKEN_FILE=str(Path(td)/"token"),HWM_PAIRING_CODE="123456",HWM_ENABLE_DEBUG="1")
        p=subprocess.Popen([exe,str(port)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
        try:
            wait(base);_,paired=req(base,"/pair","POST",{"code":"123456"});token=paired["token"]
            bad=socket.create_connection(("127.0.0.1",port),timeout=3);bad.sendall((f"GET /ws HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Protocol: hwm-v1, hwm-bearer.bad\r\nOrigin: chrome-extension://integration-test\r\n\r\n").encode());bad_headers=recv_until(bad,b"\r\n\r\n");assert bad_headers.startswith(b"HTTP/1.1 401 "),bad_headers;assert b"101 Switching Protocols" not in bad_headers;bad.close()
            ws=connect_ws(port,token);first=recv_frame(ws);assert first["type"]=="state" and first["status"]["revision"]==0,first
            assert req(base,"/debug/demo-state","POST",{},token)[0]==200
            pushed=recv_frame(ws);assert pushed["type"]=="state",pushed;st=pushed["status"];assert st["revision"]>=1 and st["state_hash"] and st["side_to_act"]==1 and st["active_entity_uid"],st
            ws.close();print("local websocket revision stream: PASS",st["revision"],st["state_hash"])
        finally:p.terminate();p.wait(timeout=5)
if __name__=="__main__":main()
