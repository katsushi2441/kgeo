# Kurage GEO

Kurage GEOは、WebサイトのAI検索対応を日本語で監査し、AI回答におけるブランド言及と自社URL引用を記録するマルチユーザー対応のGEOワークスペースです。

## 現在の実装範囲

- 公開URLのGEO技術監査（robots.txt、llms.txt、JSON-LD、meta、本文、更新シグナル、AI discovery、ブランド整合性）
- 日本語専用AEO監査（結論先出し、定義文、質問回答、根拠、読みやすさ、検索意図、主張リスク）
- GEO Optimizerが生成する47項目の引用適性、RAG、文脈効率、検索意図、信頼性、プラットフォーム別準備度の可視化
- 100点スコア、カテゴリ別内訳、根拠付き改善案、履歴保存
- 対象ページ本文を根拠としてGemma 4／DeepSeekが回答可能性・不足情報・改善案を評価
- 管理者のGemma 4はRQDB4AIの`ollama-192-168-0-14-web`キュー経由で直列実行
- LLM回答本文、使用モデル、回答可能性、根拠、不足情報、改善案の履歴表示
- ローカルSQLite／Cloud Run本番Cloud SQL PostgreSQLによるユーザー別データ分離
- 内部トークン＋信頼済みユーザーヘッダー方式のFastAPI
- 共通X認証を前段に置くPHPゲートウェイ
- Xアカウントごとに初回診断無料、2回目以降は1診断200円または20,000 URLAI
- PayPal決済とBase上のURLAI送金をサーバ側で検証し、成功した診断だけクレジットを消費
- AI回答シミュレーションは月ごとの設定可能な無料枠
- Cloud Run向けDockerfile（デプロイはローカル試験完了後に実施）

## OSSの使い分け

- `vendor/geo-optimizer-skill`: 安全なURL取得と決定論的なGEO監査エンジンとして使用。
- `vendor/ai-cmo`: AI可視性、競合、監視質問、実行履歴というプロダクト構成の参照実装。Kurage GEOは依存サービスを直接起動せず、必要なデータモデルを軽量に再実装しています。

どちらもMIT Licenseです。固定コミットはGit submoduleで管理しています。詳細は `THIRD_PARTY.md` を参照してください。

## ローカル起動

```bash
git submodule update --init --recursive
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
# .env の KGEO_INTERNAL_TOKEN を必ず変更
set -a; source .env; set +a
.venv/bin/python -m app
```

開発時のURLは `http://127.0.0.1:18308/` です。内部トークンを設定した場合、APIには `X-KGeo-Token` と `X-KGeo-User` が必要です。ブラウザへ内部トークンを公開せず、公開環境ではPHPゲートウェイから付与します。

## Kurage公開環境

ローカルFastAPIとHeteml側PHPで同じ内部トークンを使う設定を生成し、公開ファイルを配置します。

```bash
.venv/bin/python scripts/configure_runtime.py
install -m 0644 systemd/kgeo.service ~/.config/systemd/user/kgeo.service
systemctl --user daemon-reload
systemctl --user enable --now kgeo.service
scripts/deploy.sh
```

公開URLは `https://kurage.exbridge.jp/kgeo.php` です。`public/kgeo_config.php` と `.env` は秘密情報を含むためGit管理外です。

診断課金は公開PHPゲートウェイで処理します。1回目の成功した診断は無料で、2回目以降は
PayPalの200円決済またはBase上の20,000 URLAI送金で追加した診断クレジットを1消費します。
支払い済み注文・送金ログは再利用できず、監査APIが失敗した場合はクレジットを消費しません。

OGP画像を再生成する場合は `.venv/bin/python scripts/build_ogp.py` を実行します。生成元は `assets/ogp/`、公開画像は `static/images/kgeo-ogp.png`（1200×630）です。

## 根拠付きLLM回答シミュレーション

AI回答の確認はXユーザー名で自動振り分けします。管理者 `xb_bittensor` は
RQDB4AI経由で`192.168.0.14`のOllama、それ以外の一般ユーザーはDeepSeekを利用します。
Cloud Runは0.14へ直接接続しません。`queue=auto`と`ollama_host=192.168.0.14`を指定して
`ollama-192-168-0-14-web`へ振り分け、ジョブの最終結果まで待ちます。Gemma 4のジョブは
OllamaネイティブAPIへ`think: false`を明示します。

```dotenv
KGEO_ADMIN_USERS=xb_bittensor
KGEO_RQDB4AI_URL=http://127.0.0.1:18300
KGEO_RQDB4AI_TOKEN=secret
KGEO_RQDB4AI_FUNCTION=kgeo.jobs.ollama_chat_job
KGEO_OLLAMA_BASE_URL=http://192.168.0.14:11434
KGEO_OLLAMA_MODEL=gemma4:12b-it-qat
KGEO_DEEPSEEK_BASE_URL=https://api.deepseek.com
KGEO_DEEPSEEK_API_KEY=secret
KGEO_DEEPSEEK_MODEL=deepseek-v4-flash
```

秘密を別ファイルから読む場合は `KGEO_DEEPSEEK_API_KEY_FILE` と、そのファイル内の
変数名を示す `KGEO_DEEPSEEK_API_KEY_NAME` を設定できます。対象ページの公開本文をLLMへ渡し、
その本文だけで質問へ答えられるかをJSON形式で評価します。これはChatGPT、Gemini、Perplexity
などの実際の検索結果や掲載順位ではありません。画面でも「対象ページ本文を使ったシミュレーション」
と明記し、GEO技術監査、日本語AEO準備度、外部AI検索での実測を混同しないようにしています。

## テスト

```bash
.venv/bin/pytest -q
.venv/bin/ruff check app tests
php tests/test_billing.php
```

## Cloud Run

Cloud RunではCloud SQL PostgreSQLを使用し、SQLiteをコンテナへ持ち込みません。構築・移行は
次の順で実行します。現在のローカルAPIはCloud Runのヘルス確認とデータ件数検証が終わるまで
停止せず、最後にPHPゲートウェイの接続先だけを切り替えます。

```bash
scripts/configure_rqdb4ai_access.py
systemctl --user restart rqdb4ai-api.service rqdb4ai-web-worker.service
sudo tailscale set --operator="$USER"
tailscale funnel --bg --yes 18300
export KGEO_RQDB4AI_PUBLIC_URL=https://<このホストのMagicDNS名>
scripts/bootstrap_cloud_run.sh
scripts/deploy_cloud_run.sh
```

`bootstrap_cloud_run.sh`は課金が無効なら、リソースを作らず終了します。緊急時は
`scripts/rollback_to_local.sh`でPHPゲートウェイをローカルAPIへ戻せます。詳細は
`OPERATIONS.md`を参照してください。Cloud RunからHTTPのRQDB4AI公開ポートへBearerトークンを
送る構成は禁止し、Tailscale FunnelなどのHTTPS入口だけを指定します。
