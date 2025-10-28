import os
import json
import time
from queue import Queue, Empty
from flask import Flask, Response, request, jsonify, make_response

app = Flask(__name__)

# ==== Simple broker for SSE replies ====
SSE_QUEUE = Queue()

# ==== Tool definition (MCP JSON-RPC 用) ====
TOOLS_SPEC = [
    {
        "name": "echo",
        "description": "Echo back the provided text.",
        # JSON Schema (function-calling互換)
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to echo back"}
            },
            "required": ["text"],
            "additionalProperties": False
        }
    }
]

# ---- Utility: push JSON to SSE as an "rpc" event ----
def push_rpc(id_, result=None, error=None):
    payload = {"id": id_}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    SSE_QUEUE.put(("rpc", payload))

def sse_event(event: str, data: dict) -> str:
    return f"event: {event}\n" + "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"

# ================= Health =================
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

# ================= MCP SSE (server->client) =================
@app.route("/mcp", methods=["GET"])
def mcp_sse():
    def stream():
        # 初回に ready通知（任意だがデバッグしやすい）
        yield sse_event("ready", {"tools": TOOLS_SPEC})
        last_ping = 0
        while True:
            # JSON-RPCレスポンスを流す
            try:
                ev, payload = SSE_QUEUE.get_nowait()
                yield sse_event(ev, payload)
            except Empty:
                pass
            now = time.time()
            if now - last_ping > 15:
                yield sse_event("ping", {"ts": int(now)})
                last_ping = now
            time.sleep(0.2)

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Access-Control-Allow-Origin": "*",
    }
    return Response(stream(), headers=headers)

# (CORS/プリフライト保険)
@app.route("/mcp", methods=["OPTIONS"])
def mcp_options():
    resp = make_response(("", 204))
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "*"
    return resp

# ================= MCP JSON-RPC (client->server) =================
@app.route("/mcp", methods=["POST"])
def mcp_rpc():
    """
    ChatGPT Custom MCP からの JSON-RPC を受ける。
    期待メソッド:
      - tools/list -> { tools: [...] }
      - tools/call { name, arguments } -> { content: ... }
    返信は SSE 側へ event: rpc として流す（idでひも付け）。
    """
    req = request.get_json(force=True, silent=True) or {}
    id_ = req.get("id")  # ChatGPT側が付ける相関ID
    method = (req.get("method") or "").strip()
    params = req.get("params") or {}

    try:
        if method == "tools/list":
            # ChatGPT が最初にアクション定義をビルドする時に呼ぶ
            result = {"tools": TOOLS_SPEC}
            push_rpc(id_, result=result)
        elif method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if name == "echo":
                text = str(arguments.get("text", ""))
                # 返却フォーマットは任意。contentに文字列を入れておく
                result = {"content": f"Hello, {text} from MCP JSON-RPC!"}
                push_rpc(id_, result=result)
            else:
                push_rpc(id_, error={"code": -32601, "message": f"Unknown tool: {name}"})
        else:
            push_rpc(id_, error={"code": -32601, "message": f"Unknown method: {method}"})
    except Exception as e:
        push_rpc(id_, error={"code": -32603, "message": f"Server error: {e}"})

    # 受領OKだけ即時返す（実体の応答は SSE 側）
    resp = jsonify({"ok": True})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp, 200

# ===== /sse alias (UIのプレースホルダ互換) =====
@app.route("/sse", methods=["GET"])
def mcp_sse_alias():
    return mcp_sse()

# ===== Local run (RenderはProcfileのgunicornを使用) =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, threaded=True)
