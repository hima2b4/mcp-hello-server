
import os
import json
import time
from queue import Queue, Empty
from flask import Flask, Response, request, jsonify

app = Flask(__name__)

INVOKE_QUEUE = Queue()

TOOLS_SPEC = [
    {
        "name": "echo",
        "description": "Echo back the provided text.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False
        }
    }
]

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

def sse_format(event, data):
    return f"event: {event}\n" + "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"

@app.route("/mcp", methods=["GET"])
def mcp_sse():
    def stream():
        # announce ready/tools
        yield sse_format("ready", {"tools": TOOLS_SPEC})
        last_ping = 0
        while True:
            # forward invocation results if any
            try:
                result_payload = INVOKE_QUEUE.get_nowait()
                yield sse_format("result", result_payload)
            except Empty:
                pass
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

    INVOKE_QUEUE.put(result)
    return jsonify(result), 200

@app.route("/sse", methods=["GET"])
def mcp_sse_alias():
    return mcp_sse()

@app.route("/mcp", methods=["OPTIONS"])
def mcp_options():
    from flask import make_response
    resp = make_response(("", 204))
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "*"
    return resp

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, threaded=True)
