"""実サイトを相手に、メタ情報とJSON-LDの生成を通しで確認する。

単体テストはスタブLLMなので、実際のモデル出力が seo.create_metadata へ
渡せる形で返ってくるか（JSONで返すか、余計な前置きを付けないか）は
これでしか分からない。

実行: .venv/bin/python scripts/check_seo_artifacts.py [URL]
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import artifact_service, audit_service


async def main(site_url: str) -> int:
    print(f"対象: {site_url}\n")

    context = await asyncio.to_thread(audit_service.fetch_site_context, site_url)
    print(f"本文を取得: {len(context)} 文字\n")

    # 管理者扱いで走らせる（ローカルGemma側・課金しない）
    owner = "xb_bittensor"
    out = await artifact_service.generate(
        site_url, "株式会社エクスブリッジ", [artifact_service.META, artifact_service.JSON_LD],
        owner, paid=False,
    )
    print(f"provider={out['provider']} model={out['model']}\n")

    meta = out["artifacts"][artifact_service.META]
    print("--- メタ情報 ---")
    print(f"valid={meta['valid']} {meta['invalid_reason']}")
    print(meta["content"] or "(空)")

    jsonld = out["artifacts"][artifact_service.JSON_LD]
    print("\n--- JSON-LD ---")
    print(f"valid={jsonld['valid']} {jsonld['invalid_reason']}")
    print(jsonld["content"][:600])

    # 埋め込みが壊れていないこと（閉じタグは末尾の1つだけ）
    problems = []
    if jsonld["content"].count("</script>") != 1:
        problems.append("JSON-LDに </script> が複数ある（タグが途中で閉じている）")
    if meta["valid"] and "<title>" not in meta["content"]:
        problems.append("メタ情報に <title> が無い")

    # 生成したJSON-LDが、監査器の見る形に戻せること
    body = jsonld["content"].split(">", 1)[1].rsplit("<", 1)[0]
    restored = body.replace("\\u003c", "<").replace("\\u003e", ">").replace("\\u0026", "&")
    try:
        json.loads(restored)
    except json.JSONDecodeError as exc:
        problems.append(f"エスケープを戻してもJSONにならない: {exc}")

    print("\n=== 判定 ===")
    for line in problems:
        print("NG ", line)
    if not problems:
        print("ok  生成物はそのまま設置できる形です")
    return 1 if problems else 0


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://exbridge.jp/"
    raise SystemExit(asyncio.run(main(url)))
