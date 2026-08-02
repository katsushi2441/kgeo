# Kurage GEO Operations

## Local service

- Service name: `kgeo`
- Default bind: `127.0.0.1:18308`
- Health: `GET /health`
- Persistent local data: `data/kgeo.db`
- Secrets: `.env` and deployed `public/kgeo_config.php`（いずれもGit管理外）

systemdユーザーサービスとして使う場合は、`.env`を作成してから `systemd/kgeo.service` を `~/.config/systemd/user/` に配置します。サービスの導入・起動はローカル試験合格後に行います。

公開配置では `scripts/configure_runtime.py` で秘密設定を生成し、`systemd/kgeo.service` を `~/.config/systemd/user/` へ配置してから、`scripts/deploy.sh` で `kgeo.php`、`kgeo_app.html`、`assets/kgeo.css`、`assets/kgeo.js`、秘密設定をHetemlへ配置します。

## Security boundary

公開ブラウザ → 共通X認証付き `kgeo.php` → FastAPI の順に接続します。PHPだけが内部トークンを保持し、認証済みXユーザーを `X-KGeo-User` で渡します。FastAPIを直接インターネット公開しない構成を基本とします。

監査対象URLはGEO Optimizerの検証器を通し、loopback、private、link-local、reserved IPと危険なリダイレクトを拒否します。レスポンス本文も上限付きストリームで取得します。

## Cloud Run migration gate

Cloud Runへ移す前に次を完了させます。

1. API、ユーザー分離、SSRF、無料枠、モックLLMの自動テストが合格
2. スマートフォンを含む画面操作試験が合格
3. Cloud SQL PostgreSQLへのDB移行とマイグレーション試験
4. Secret Managerへ内部トークン・LLMキーを登録
5. Cloud Runは認証付きingressにし、PHPゲートウェイだけが呼べる経路を確認
6. CPU・タイムアウト・最大インスタンス数を設定し、意図しない課金を防止
7. 監査キューまたはCloud Tasks導入を負荷試験で判断

現行Dockerfileはコンテナ互換性の確認用です。SQLiteのまま本番デプロイしません。
