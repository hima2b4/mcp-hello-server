import os
import json
import time
from queue import Queue, Empty
from flask import Flask, Response, request, jsonify, make_response

app = Flask(__name__)

# ========= In-memory queue for SSE =========
SSE_QUEUE = Queue()

# ========= Tools (function-calling 互換スキーマ) =========
TOOLS_SPEC = [
    {
        "name": "echo",
        "description": "Echo back the provided text.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to echo back"}
            },
            "required": ["text"],
            "additionalProperties": False
        },
    }
]

# ========= Utilities =========
def sse_event(event: str, data: dict) -> str:
    return f"event: {event}\n" + "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"

def jsonrpc_result(id_, result):
    return {"jsonrpc": "2.0", "id": id_, "result": result}

def jsonrpc_error(id_, code, message):
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}

def push_rpc_to_sse(id_, result=None, error=None):
    payload = {"jsonrpc": "2.0", "id": id_}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    SSE_QUEUE.put(("rpc", payload))

# ========= Health =========
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

# ========= MCP: SSE (server -> client) =========
@app.route("/mcp", methods=["GET"])
def mcp_sse():
    def stream():
        # 初回に ready 通知（ツール一覧）
        yield sse_event("ready", {"tools": TOOLS_SPEC})
        last = 0
        while True:
            try:
                ev, payload = SSE_QUEUE.get_nowait()
                yield sse_event(ev, payload)
            except Empty:
                pass
            now = time.time()
            if now - last > 15:
                yield sse_event("ping", {"ts": int(now)})
                last = now
            time.sleep(0.2)

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Access-Control-Allow-Origin": "*",
    }
    return Response(stream(), headers=headers)

# プレフライト/ヘルス系
@app.route("/mcp", methods=["OPTIONS", "HEAD"])
def mcp_meta():
    resp = make_response(("", 204))
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, HEAD"
    resp.headers["Access-Control-Allow-Headers"] = "*"
    return resp

# ========= MCP: JSON-RPC (client -> server) =========
@app.route("/mcp", methods=["POST"])
def mcp_rpc():
    req = request.get_json(force=True, silent=True) or {}
    id_ = req.get("id")
    method = (req.get("method") or "").strip()
    params = req.get("params") or {}

    try:
        if method == "tools/list":
            result = {"tools": TOOLS_SPEC}
            # 同期応答
            body = jsonrpc_result(id_, result)
            # ついでにSSEにも流す（デバッグ観察用）
            push_rpc_to_sse(id_, result=result)

        elif method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if name == "echo":
                text = str(arguments.get("text", ""))
                result = {"content": f"Hello, {text} from MCP JSON-RPC sync!"}
                body = jsonrpc_result(id_, result)
                push_rpc_to_sse(id_, result=result)
            else:
                err = {"code": -32601, "message": f"Unknown tool: {name}"}
                body = jsonrpc_error(id_, **err)
                push_rpc_to_sse(id_, error=err)

        else:
            err = {"code": -32601, "message": f"Unknown method: {method}"}
            body = jsonrpc_error(id_, **err)
            push_rpc_to_sse(id_, error=err)

    except Exception as e:
        err = {"code": -32603, "message": f"Server error: {e}"}
        body = jsonrpc_error(id_, **err)
        push_rpc_to_sse(id_, error=err)

    resp = jsonify(body)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, HEAD"
    return resp, 200

# ========= /sse alias =========
@app.route("/sse", methods=["GET"])
def mcp_sse_alias():
    return mcp_sse()

# ========= Local run =========
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, threaded=True)
