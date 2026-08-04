"""メタ情報とJSON-LDを、そのまま貼れるHTMLとして組み立てる。

next-forge の `packages/seo`（MIT / Vercel）をPythonへ移植したもの。
移植したのは次の2点で、どちらもベンダーに依存しない純粋な処理:

- `escapeJsonForHtml` → `escape_json_for_html`
  JSON-LDを <script> の中に置くとき、`<` `>` `&` と行区切り文字を
  \\uXXXX へ逃がす。これが無いと本文に `</script>` を含むJSONで
  スクリプトタグが途中で閉じ、顧客サイトに任意のHTMLを差し込める。
  生成元はLLMの出力なので、内容を信用して埋め込んではいけない。
- `createMetadata` → `create_metadata`
  title/description/image から OGP・Twitter Card・canonical などを
  一括で組む。監査で「meta description が無い」「OGPが無い」と出た
  サイトへ、文面ではなく貼れる現物を渡すために使う。

LLMは使わない。決まった書式に落とすだけの処理で、生成の揺れは
そのまま不良品になるため。
"""

from __future__ import annotations

import html
import json
from typing import Any

# Google推奨に合わせた寸法。OGP画像はこの比率で用意してもらう。
OG_IMAGE_WIDTH = 1200
OG_IMAGE_HEIGHT = 630


def escape_json_for_html(payload: str) -> str:
    """JSON文字列を <script> の中へ安全に置ける形にする。

    `</script>` で閉じられるのを防ぐために `<` `>` を、HTMLエンティティ
    として解釈されうる `&` を、JavaScriptで行終端と見なされる
    U+2028 / U+2029 を、それぞれ \\uXXXX へ置き換える。
    JSONとしての値は変わらないので、パーサ側の解釈は同じになる。
    """
    return (
        payload.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace(" ", "\\u2028")
        .replace(" ", "\\u2029")
    )


def json_ld_script(data: Any, *, indent: int | None = 2) -> str:
    """JSON-LDを <script type="application/ld+json"> で包んで返す。

    data は dict でも、JSON文字列でもよい（LLM出力をそのまま渡せる）。
    文字列が壊れたJSONのときは、直さずそのまま包む。正否の判定は
    artifact_service 側の検証に任せ、ここでは埋め込みの安全だけを見る。
    """
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return (
                '<script type="application/ld+json">\n'
                f"{escape_json_for_html(data.strip())}\n"
                "</script>"
            )
    body = json.dumps(data, ensure_ascii=False, indent=indent)
    return f'<script type="application/ld+json">\n{escape_json_for_html(body)}\n</script>'


def _meta(name: str, content: str, *, prop: bool = False) -> str:
    attr = "property" if prop else "name"
    return f'<meta {attr}="{html.escape(name, quote=True)}" content="{html.escape(content, quote=True)}">'


def create_metadata(
    *,
    title: str,
    description: str,
    url: str = "",
    image: str = "",
    site_name: str = "",
    locale: str = "ja_JP",
    twitter_handle: str = "",
) -> str:
    """<head> にそのまま貼れるメタ情報一式を組み立てる。

    next-forge の createMetadata と同じ項目を出す。あちらは Next.js の
    Metadata オブジェクトを返すが、こちらは設置してもらうのが目的なので
    HTMLの文字列で返す。
    """
    title = title.strip()
    description = description.strip()
    if not title or not description:
        raise ValueError("title と description は必須です")
    site_name = site_name.strip() or title
    # next-forge は常に "title | applicationName" にするが、こちらの title は
    # LLMがサイト本文から書くのでブランド名を含んでいることがある。そのまま
    # 足すと「A社 | 事業内容 | A社」になる。含んでいたら足さない。
    full_title = title if site_name in title else f"{title} | {site_name}"

    lines = [
        f"<title>{html.escape(full_title)}</title>",
        _meta("description", description),
        _meta("application-name", site_name),
        # 本文中の数字が勝手に電話番号リンクにされるのを防ぐ（next-forge と同じ）
        _meta("format-detection", "telephone=no"),
    ]
    if url:
        lines.append(f'<link rel="canonical" href="{html.escape(url, quote=True)}">')

    lines += [
        "",
        _meta("og:type", "website", prop=True),
        _meta("og:locale", locale, prop=True),
        _meta("og:title", full_title, prop=True),
        _meta("og:description", description, prop=True),
        _meta("og:site_name", site_name, prop=True),
    ]
    if url:
        lines.append(_meta("og:url", url, prop=True))
    if image:
        lines += [
            _meta("og:image", image, prop=True),
            _meta("og:image:width", str(OG_IMAGE_WIDTH), prop=True),
            _meta("og:image:height", str(OG_IMAGE_HEIGHT), prop=True),
            _meta("og:image:alt", full_title, prop=True),
        ]

    lines += [
        "",
        _meta("twitter:card", "summary_large_image" if image else "summary"),
    ]
    if image:
        lines.append(_meta("twitter:image", image))
    if twitter_handle:
        handle = twitter_handle if twitter_handle.startswith("@") else f"@{twitter_handle}"
        lines.append(_meta("twitter:creator", handle))

    # iOSでホーム画面に追加したときの表示（next-forge の appleWebApp 相当）
    lines += [
        "",
        _meta("apple-mobile-web-app-capable", "yes"),
        _meta("apple-mobile-web-app-status-bar-style", "default"),
        _meta("apple-mobile-web-app-title", full_title),
    ]
    return "\n".join(lines)
