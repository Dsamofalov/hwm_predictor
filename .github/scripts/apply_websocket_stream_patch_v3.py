from pathlib import Path

old=Path('.github/scripts/apply_websocket_stream_patch.py')
source=old.read_text(encoding='utf-8')
source=source.replace(
    "SCRIPT=ROOT/'.github/scripts/apply_websocket_stream_patch.py'",
    "SCRIPT=ROOT/'.github/scripts/apply_websocket_stream_patch_v3.py'",
    1,
)

# Negative handshake checks the HTTP status code rather than the shared helper's
# intentionally generic reason phrase.
source=source.replace(
    'assert b"401 Unauthorized" in recv_until(bad,b"\\r\\n\\r\\n");bad.close()',
    'bad_headers=recv_until(bad,b"\\r\\n\\r\\n");assert bad_headers.startswith(b"HTTP/1.1 401 "),bad_headers;assert b"101 Switching Protocols" not in bad_headers;bad.close()',
    1,
)

# Warning-clean generated C++ helpers.
source=source.replace(
    'if(comma==std::string::npos)break;pos=comma+1;',
    'if(comma==std::string::npos) break;\n        pos=comma+1;',
    1,
)
source=source.replace(
    'if(n<=0)return false;off+=static_cast<size_t>(n);}return true;}',
    'if(n<=0) return false;\n    off+=static_cast<size_t>(n);\n    }\n    return true;\n}',
    1,
)
source=source.replace(
    'if(send_all(client,hs.str()))websocket_stream(client,store_,stop_);close_sock(client);return;',
    'if(send_all(client,hs.str())) websocket_stream(client,store_,stop_);\n                close_sock(client);\n                return;',
    1,
)

# The project intentionally uses a lightweight chrome global declaration rather
# than @types/chrome, so explicitly type this listener under strict TS settings.
source=source.replace(
    'chrome.storage.onChanged.addListener((changes,area)=>',
    'chrome.storage.onChanged.addListener((changes:any,area:string)=>',
    1,
)

# Remove all generations of one-shot WS patch tooling from the functional tree.
source=source.replace(
    'WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True)',
    "WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True);old.unlink(missing_ok=True);Path('.github/scripts/apply_websocket_stream_patch_v2.py').unlink(missing_ok=True)",
    1,
)

exec(compile(source,'<websocket-stream-patcher-v3>','exec'),{
    '__name__':'__main__',
    '__file__':str(old),
    'old':old,
    'Path':Path,
})
