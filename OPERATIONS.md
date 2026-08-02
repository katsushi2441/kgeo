# Kurage GEO Operations

## Local service

- Service name: `kgeo`
- Default bind: `127.0.0.1:18308`
- Health: `GET /health`
- Persistent local data: `data/kgeo.db`
- Secrets: `.env`、`public/kgeo_config.php`、`public/kgeo_db_config.php`（Git管理外）

systemdユーザーサービスとして使う場合は、`.env`を作成してから `systemd/kgeo.service` を `~/.config/systemd/user/` に配置します。サービスの導入・起動はローカル試験合格後に行います。

公開配置では `scripts/configure_runtime.py` で秘密設定を生成し、`systemd/kgeo.service` を `~/.config/systemd/user/` へ配置してから、`scripts/deploy.sh` で `kgeo.php`、`kgeo_app.html`、`assets/kgeo.css`、`assets/kgeo.js`、秘密設定をHetemlへ配置します。

## Security boundary

公開ブラウザ → 共通X認証付き`kgeo.php` → Cloud Run FastAPIの順に接続します。
FastAPIはHeteml上の内部トークン付き`kgeo_store.php`を経由して、Heteml MySQLへ保存します。
DBパスワードはHeteml内のGit管理外PHP設定だけに置き、Cloud Runへは渡しません。

AI回答モニタリングは認証済みXユーザーで振り分けます。`xb_bittensor` は
Cloud RunからRQDB4AIへ投入し、`ollama-192-168-0-14-web`で直列化した上で
`192.168.0.14:11434`の`gemma4:12b-it-qat`を使います。それ以外はDeepSeekです。
Cloud Runから0.14を直接呼び出す経路は作りません。管理者名は`@`を除去して小文字化して
比較します。RQジョブはOllamaの`/api/chat`へ`think: false`を渡します。

監査対象URLはGEO Optimizerの検証器を通し、loopback、private、link-local、reserved IPと危険なリダイレクトを拒否します。レスポンス本文も上限付きストリームで取得します。

## Cloud Run migration

Cloud Runへ移す前に次を完了させます。

1. API、ユーザー分離、SSRF、無料枠、モックLLMの自動テストが合格
2. スマートフォンを含む画面操作試験が合格
3. `scripts/migrate_sqlite_to_heteml.py`によるHeteml MySQLへのDB移行と件数検証
4. Secret Managerへ内部トークン・LLMキーを登録
5. Heteml PHPからの呼び出しはアプリ内部トークンで認証し、ブラウザへトークンを公開しない
6. CPU・タイムアウト・最大インスタンス数を設定し、意図しない課金を防止
7. 監査キューまたはCloud Tasks導入を負荷試験で判断

### 実行順序

```bash
scripts/configure_rqdb4ai_access.py
systemctl --user restart rqdb4ai-api.service rqdb4ai-web-worker.service
sudo scripts/install_rqdb4ai_https_proxy.sh
scripts/configure_heteml_storage.py --host <DBホスト> --database <DB名> --user <DBユーザー>
scripts/deploy.sh
set -a; source .env; set +a
scripts/migrate_sqlite_to_heteml.py
scripts/bootstrap_cloud_run.sh
scripts/deploy_cloud_run.sh
```

`bootstrap_cloud_run.sh`は専用サービスアカウントとSecret Managerを作成しますが、
Cloud SQLは作成しません。`deploy_cloud_run.sh`はHeteml DB APIの事前確認とCloud Runの
認証付きヘルスチェックが成功した場合だけ、HetemlのPHP接続先を切り替えます。
Cloud RunのingressはHetemlから到達できる`all`ですが、全APIは既存の
`X-KGeo-Token`で拒否・許可を判定します。最大インスタンス数は2、同時実行数は8、
リクエストタイムアウトは600秒です。

RQDB4AIの既存HTTP公開ポートへCloud RunからBearerトークンを送ってはいけません。
既存の`exbridge.ddns.net:8012`のNginx/SSLにkgeo専用の限定経路を追加し、Cloud Run用の
`KGEO_RQDB4AI_PUBLIC_URL`は既定で
`https://exbridge.ddns.net:8012/kgeo-rqdb4ai`を使います。導入スクリプトは元設定を退避し、
`nginx -t`失敗時には自動で復元します。両デプロイスクリプトもHTTPSと`/healthz`を
事前検証します。0.14 Ollama自体は公開しません。

ロールバック:

```bash
scripts/rollback_to_local.sh
```

本番データはHeteml MySQLに保存され、Cloud Runの一時ディスクには保存しません。
