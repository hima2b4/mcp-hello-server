import os
import json
import time
from flask import Flask, Response, request, jsonify, make_response

app = Flask(__name__)

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

# ========= Health =========
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

# ========= MCP: SSE (server -> client)  ※短命SSEで即返してタイムアウト回避 =========
@app.route("/mcp", methods=["GET"])
def mcp_sse():
    def stream():
        # 初回通知だけ送ってすぐ終了（Render Free の worker timeout を避ける）
        yield sse_event("ready", {"tools": TOOLS_SPEC})
        yield sse_event("ping", {"ts": int(time.time())})

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Access-Control-Allow-Origin": "*",
    }
    return Response(stream(), headers=headers)

# プレフライト/検証用
@app.route("/mcp", methods=["OPTIONS", "HEAD"])
def mcp_meta():
    resp = make_response(("", 204))
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, HEAD"
    resp.headers["Access-Control-Allow-Headers"] = "*"
    return resp

# ========= MCP: JSON-RPC (client -> server)  ※同期応答 =========
@app.route("/mcp", methods=["POST"])
def mcp_rpc():
    req = request.get_json(force=True, silent=True) or {}
    id_ = req.get("id")
    method = (req.get("method") or "").strip()
    params = req.get("params") or {}

    try:
        if method == "tools/list":
            body = jsonrpc_result(id_, {"tools": TOOLS_SPEC})
        elif method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if name == "echo":
                text = str(arguments.get("text", ""))
                body = jsonrpc_result(id_, {"content": f"Hello, {text} from MCP JSON-RPC sync!"})
            else:
                body = jsonrpc_error(id_, -32601, f"Unknown tool: {name}")
        else:
            body = jsonrpc_error(id_, -32601, f"Unknown method: {method}")
    except Exception as e:
        body = jsonrpc_error(id_, -32603, f"Server error: {e}")

    resp = jsonify(body)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, HEAD"
    return resp, 200

# ========= /sse alias（UIの表記ゆれ対策） =========
@app.route("/sse", methods=["GET"])
def mcp_sse_alias():
    return mcp_sse()

# ========= Local run (RenderはProcfileでgunicorn起動) =========
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, threaded=True)

