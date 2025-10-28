
# Minimal MCP Server on Render (Free Plan)

ChatGPT から呼び出せる最小の **MCP (Model Context Protocol) 風エンドポイント** を
Render の無料プランで公開するテンプレートです。

> エンドポイント: `POST /mcp` (JSON)  
> ヘルスチェック: `GET /health`

---

## 1) 使い方（GitHub → Render）

1. **このリポジトリを作成**（またはZIPを展開してアップロード）  
2. `render.yaml` と `Procfile` があることを確認  
3. [Render](https://render.com/) にログイン → 「New」→「Web Service」  
   - GitHub と連携して本リポジトリを選択  
   - プランは **Free** でOK  
   - Build: `pip install -r requirements.txt`  
   - Start: `gunicorn server:app --bind 0.0.0.0:$PORT`  
4. デプロイが終わると **固定URL** が発行されます  
   例: `https://mcp-hello.onrender.com`

### 動作確認
- `GET https://<your-app>.onrender.com/health` → `{"status":"ok"}`  
- `POST https://<your-app>.onrender.com/mcp`  
  ```json
  {"input":"Hello"}
  ```
  応答例:
  ```json
  {"output":"Hello, Hello from Render MCP!","echo":{"input":"Hello"}}
  ```

---

## 2) ChatGPT での登録（開発者モード）

1. ChatGPT 右上の設定 → **開発者モード** を有効化  
2. 「＋新規ツール」→ 任意の名前（例: Render MCP）  
3. **MCPサーバーURL** に以下を入力  
   ```
   https://<your-app>.onrender.com/mcp
   ```
4. 認証は「なし」でOK → 作成  
5. チャット欄の「＋」からツールを選び、`Hello` など入力して応答を確認

---

## 3) カスタマイズ（Sora2 等の外部API連携）

`server.py` の `/mcp` ハンドラ内に外部API呼び出しを追加します。  
APIキーは Render の **Environment** に設定し、`os.environ["API_KEY"]` で参照してください。  
（`.env` はローカル開発時のみ。`render.yaml` には秘密情報を書かないこと）

---

## 4) 構成ファイルについて

- `server.py` : Flask 本体（`/mcp`, `/health`）  
- `requirements.txt` : 依存ライブラリ（Flask, Gunicorn）  
- `Procfile` : Render の起動コマンド  
- `render.yaml` : Render のサービス定義（Free プラン/リージョン等）  
- `.env.example` : 環境変数のサンプル（APIキーなどをここに書いて `.env` にコピー）  
- `.gitignore` : 秘密情報や不要ファイルを除外

---

## 5) ライセンス
MIT License（任意に変更可）
