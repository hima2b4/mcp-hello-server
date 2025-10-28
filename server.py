
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/mcp", methods=["POST"])
def mcp():
    try:
        data = request.get_json(force=True, silent=True) or {}
    except Exception:
        data = {}
    user_input = (data.get("input") or "").strip()
    # ここに外部API呼び出しや業務ロジックを追加できます。
    # 例: Sora2 API を呼ぶ、ファイル処理をする、など。
    return jsonify({
        "output": f"Hello, {user_input or 'World'} from Render MCP!",
        "echo": data
    }), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
