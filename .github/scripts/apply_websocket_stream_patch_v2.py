from pathlib import Path

old=Path('.github/scripts/apply_websocket_stream_patch.py')
source=old.read_text(encoding='utf-8')
source=source.replace(
    "SCRIPT=ROOT/'.github/scripts/apply_websocket_stream_patch.py'",
    "SCRIPT=ROOT/'.github/scripts/apply_websocket_stream_patch_v2.py'",
    1,
)

# Keep the negative auth gate semantic: the shared HTTP helper intentionally uses
# a generic reason phrase (`401 Error`), so assert the numeric status and absence
# of a successful WebSocket upgrade rather than cosmetic reason text.
source=source.replace(
    'assert b"401 Unauthorized" in recv_until(bad,b"\\r\\n\\r\\n");bad.close()',
    'bad_headers=recv_until(bad,b"\\r\\n\\r\\n");assert bad_headers.startswith(b"HTTP/1.1 401 "),bad_headers;assert b"101 Switching Protocols" not in bad_headers;bad.close()',
    1,
)

# Remove misleading-indentation warnings from the generated C++ while preserving
# behavior. These are source-generation fixes only.
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

# Functional tree must remove both generations of one-shot tooling.
source=source.replace(
    'WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True)',
    "WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True);old.unlink(missing_ok=True)",
    1,
)

exec(compile(source,'<websocket-stream-patcher-v2>','exec'),{
    '__name__':'__main__',
    '__file__':str(old),
    'old':old,
})
