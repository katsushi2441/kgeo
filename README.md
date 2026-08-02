# Kurage GEO

Kurage GEOは、WebサイトのAI検索対応を日本語で監査し、AI回答におけるブランド言及と自社URL引用を記録するマルチユーザー対応のGEOワークスペースです。

## 現在の実装範囲

- 公開URLのGEO技術監査（robots.txt、llms.txt、JSON-LD、meta、本文、更新シグナル、AI discovery、ブランド整合性）
- 100点スコア、カテゴリ別内訳、改善案の日本語表示、履歴保存
- OpenAI互換LLMを利用した検索質問モニタリング
- ブランド言及、自社ドメイン引用、引用順位、引用URLの保存
- SQLiteによるユーザー別データ分離
- 内部トークン＋信頼済みユーザーヘッダー方式のFastAPI
- 共通X認証を前段に置くPHPゲートウェイ
- 月ごとの設定可能な無料枠
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

## AI回答モニタリング

以下を設定するとAI回答の確認が有効になります。未設定でも技術監査はすべて利用できます。

```dotenv
KGEO_LLM_BASE_URL=https://your-openai-compatible.example/v1
KGEO_LLM_API_KEY=secret
KGEO_LLM_MODEL=your-model
```

LLMの回答は検索結果そのものを保証しません。利用するプロバイダーがWeb検索・引用URLを返せる構成かを確認し、時系列比較の観測値として扱ってください。

## テスト

```bash
.venv/bin/pytest -q
.venv/bin/ruff check app tests
```

## Cloud Run

Dockerfileは用意済みですが、現段階ではデプロイしません。SQLiteはCloud Runの一時ファイルシステムに永続化できないため、本番移行時はCloud SQL/PostgreSQLへ差し替えます。詳細は `OPERATIONS.md` を参照してください。
