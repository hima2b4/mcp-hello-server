
import os
import json
import time
from queue import Queue, Empty
from flask import Flask, Response, request, jsonify, make_response

app = Flask(__name__)

# ---- Simple in-memory queue for streaming results to SSE clients ----
INVOKE_QUEUE = Queue()

# ---- Tool definitions (ChatGPT側が解釈しやすい形式) ----
TOOLS_SPEC = [
    {
        "name": "echo",
        "description": "Echo back the provided text.",
        # function-calling 準拠のパラメータ定義
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to echo back"}
            },
            "required": ["text"],
            "additionalProperties": False
        },
        # 実行用のHTTPエンドポイントを明示
        "endpoint": {
            "path": "/invoke",
            "method": "POST"
        }
    }
]

# ---- Health check ----
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

# ---- SSE helpers ----
def sse_format(event: str, data: dict) -> str:
    return f"event: {event}\n" + "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"

# ---- Main MCP SSE endpoint (ChatGPTのカスタムMCPが接続) ----
@app.route("/mcp", methods=["GET"])
def mcp_sse():
    def stream():
        # 接続直後にツール一覧を通知
        yield sse_format("ready", {"tools": TOOLS_SPEC})
        last_ping = 0
        while True:
            # /invoke 側で得た結果をSSEに流す
            try:
                result_payload = INVOKE_QUEUE.get_nowait()
                yield sse_format("result", result_payload)
            except Empty:
                pass
            # keep-alive ping
            now = time.time()
            if now - last_ping > 15:
                yield sse_format("ping", {"ts": int(now)})
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

# プリフライト（保険）
@app.route("/mcp", methods=["OPTIONS"])
def mcp_options():
    resp = make_response(("", 204))
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "*"
    return resp

# ---- /sse エイリアス（UIのプレースホルダ互換用）----
@app.route("/sse", methods=["GET"])
def mcp_sse_alias():
    return mcp_sse()

# ---- Tool invocation endpoint ----
@app.route("/invoke", methods=["POST"])
def invoke():
    payload = request.get_json(force=True, silent=True) or {}
    tool = (payload.get("tool") or "").strip()
    args = payload.get("arguments") or {}

    if tool == "echo":
        text = str(args.get("text", ""))
        result = {"tool": tool, "ok": True, "output": f"Hello, {text} from MCP SSE!"}
    else:
        result = {"tool": tool, "ok": False, "error": f"Unknown tool: {tool}"}

    # SSE にも配信
    INVOKE_QUEUE.put(result)

    # CORS付与して返す
    resp = jsonify(result)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return resp, 200

# プリフライト（保険）
@app.route("/invoke", methods=["OPTIONS"])
def invoke_options():
    resp = make_response(("", 204))
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "*"
    return resp

# ---- Local run (RenderはProcfile経由でgunicornを使います) ----
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, threaded=True)
