"""LPに「Kurage GEO Pro（構想）」のセクションを差し込む。

まだ提供していない機能なので、**準備中であることを明示する**。
提供中と誤解される書き方は絶対にしない(ワークスペースの原則:
デモ・公開URL・完了状態を偽らない)。

現行の kgeo は「監査と提案」まで。Pro は「常時監視と修正実行」まで担う
月額版という位置づけ。何が完全自動で、何が提案止まりかを正直に書く。

何度実行しても同じ結果になる(BEGIN/ENDマーカーで置換)。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = {"ja": ROOT / "landing" / "kgeo.html", "en": ROOT / "landing" / "index.html"}
# アプリ入口(kurage.exbridge.jp/kgeo.php)は1ファイルで両言語を持つ。
PHP_PAGE = ROOT / "public" / "kgeo.php"

BEGIN = "<!-- BEGIN kurage-geo-pro (scripts/inject_pro_concept.py が生成) -->"
END = "<!-- END kurage-geo-pro -->"

STYLE = """<style>
  .pro-sec { max-width:1080px; margin:0 auto; padding:38px 20px; }
  .pro-box { background:var(--panel); border:1px solid var(--panel-line); border-radius:18px; padding:28px; }
  .pro-badge { display:inline-block; font-size:12px; font-weight:800; letter-spacing:.04em;
    background:var(--gold-bg); border:1px solid var(--gold-line); color:var(--gold);
    border-radius:999px; padding:4px 14px; margin-bottom:12px; }
  .pro-box h2 { font-size:clamp(19px,2.6vw,25px); margin-bottom:6px; }
  .pro-lead { color:var(--abyss-soft); font-size:14.5px; margin-bottom:20px; }
  .pro-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:14px; margin-bottom:20px; }
  .pro-item { background:var(--foam); border:1px solid var(--panel-line); border-radius:12px; padding:16px; }
  .pro-item h3 { font-size:14.5px; font-weight:800; margin-bottom:5px; }
  .pro-item p { font-size:12.5px; color:var(--abyss-soft); line-height:1.75; }
  .pro-table { width:100%; border-collapse:collapse; font-size:13.5px; }
  .pro-table th, .pro-table td { text-align:left; padding:9px 10px; border-bottom:1px solid var(--panel-line); }
  .pro-table th { color:var(--abyss-soft); font-size:12px; }
  .pro-auto { color:var(--teal-deep); font-weight:800; }
  .pro-manual { color:var(--abyss-soft); }
  .pro-note { font-size:12px; color:var(--abyss-soft); margin-top:16px; }
  .set-box { background:var(--foam); border:1px solid var(--panel-line); border-radius:18px;
    padding:26px; margin-top:16px; }
  .set-box h3 { font-size:16px; font-weight:800; margin-bottom:6px; }
  .set-box .set-sub { font-size:13px; color:var(--abyss-soft); margin-bottom:16px; }
  .set-cols { display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:14px; }
  .set-col { background:var(--panel); border:1px solid var(--panel-line); border-radius:12px; padding:16px; }
  .set-col h4 { font-size:13.5px; font-weight:800; margin-bottom:5px; color:var(--teal-deep); }
  .set-col p { font-size:12.5px; color:var(--abyss-soft); line-height:1.75; }
  .set-price { display:inline-block; font-size:13px; font-weight:800; color:var(--gold);
    background:var(--gold-bg); border:1px solid var(--gold-line); border-radius:999px;
    padding:5px 16px; margin-top:16px; }
  .set-links { font-size:12.5px; margin-top:12px; }
</style>"""

TEXT = {
    "ja": {
        "badge": "準備中 — まだご利用いただけません",
        "h": "Kurage GEO Pro（構想）",
        "lead": "いまの Kurage GEO は<b>監査と提案</b>までです。Pro はその先——"
                "<b>常時監視と修正の実行</b>まで受け持つ月額版として構想しています。",
        "items": [
            ("常時監視", "週次または月次で自動的に再監査し、スコアの低下を検知します。直したはずの項目が戻ったら、"
                       "自動で課題を再オープンします。"),
            ("GitHub App 連携", "サイトのリポジトリに Kurage GEO Pro をインストールしていただくと、"
                              "修正を Pull Request として提出します。レビューしてマージするだけで反映されます。"),
            ("自動で直せるものは自動で", "判断の要らない修正は検知しだい PR にします。"
                                "判断が要るものは提案に留め、内容の決定はお客様に残します。"),
            ("before / after の記録", "最初と最新の比較を月次レポートにまとめます。"
                                  "Xでそのまま共有できる要約も生成します。"),
        ],
        "table_h": ("修正内容", "Proでの扱い"),
        "rows": [
            ("llms.txt の設置・更新", "auto", "完全自動でPR"),
            ("robots.txt のAIクローラー許可", "auto", "完全自動でPR"),
            ("sitemap.xml の設置", "auto", "完全自動でPR"),
            ("JSON-LD の挿入", "manual", "提案（設置はお客様の手で）"),
            ("本文の書き直し", "manual", "提案（内容の決定はお客様）"),
        ],
        "set_h": "オプション：Kurage URL2GPTResearcher をセットに",
        "set_sub": "GEOで<b>見つけてもらう下地</b>を整えても、載っている中身が何年も同じままなら"
                   "「動いていないサイト」に見えます。更新そのものを続ける仕組みを、Proに束ねられます。",
        "set_cols": [
            ("Kurage GEO Pro がやること",
             "AIクローラーの許可、llms.txt、構造化データ、本文の構造——"
             "<b>AIに理解・引用されるための技術的な下地</b>を整え、崩れたら直します。"),
            ("Kurage URL2GPTResearcher がやること",
             "サイトの内容をAIが理解し、その事業に<b>関連する最新情報を調べて記事にし、掲載し続けます</b>。"
             "顧客サイトに置くのは表示専用のPHP1ファイルだけです。"),
            ("セットにすると",
             "監査で「更新・配信シグナルが弱い」と出たサイトに、下地の修正と"
             "<b>更新の実体</b>を同時に入れられます。監査→修正→掲載が一本の線になります。"),
        ],
        "set_price": "セット価格は応相談",
        "set_links": 'Kurage URL2GPTResearcher は<b>単体では今すぐご利用いただけます</b>（1調査 200円 または 20,000 URLAI）。'
                     '→ <a href="https://kurage.exbridge.jp/kurl2gr.php">はじめる</a> ／ '
                     '<a href="https://kurl2gr.exbridge.jp/kurl2gr.html" target="_blank" rel="noopener">サービス紹介</a>',
        "set_note": "※ セットでのご提供は Kurage GEO Pro と同じく<b>構想段階</b>です。"
                    "提供時期は未定で、価格はご相談のうえ決定します。",
        "note": "※ 本セクションは<b>構想段階の内容</b>であり、提供時期・価格・機能は未定です。"
                "現在ご利用いただけるのは、初回無料・2回目以降1診断200円（または20,000 URLAI）の"
                "GEO診断のみです。検索順位やAI回答への掲載を保証するものではありません。",
    },
    "en": {
        "badge": "In preparation — not available yet",
        "h": "Kurage GEO Pro (concept)",
        "lead": "Kurage GEO today covers <b>auditing and recommendations</b>. Pro is planned as a "
                "monthly plan that goes further — <b>continuous monitoring and applying the fixes</b>.",
        "items": [
            ("Continuous monitoring", "Re-audits automatically every week or month and detects score drops. "
                                      "If a fixed item regresses, the issue reopens by itself."),
            ("GitHub App integration", "Install Kurage GEO Pro on your site's repository and fixes arrive as "
                                       "pull requests. Review, merge, and they ship."),
            ("Automate what is safe to automate", "Fixes that need no judgement become PRs as soon as they are "
                                                  "detected. Anything that needs judgement stays a recommendation."),
            ("Before / after on record", "First-versus-latest comparison in a monthly report, plus a summary "
                                         "you can share on X as is."),
        ],
        "table_h": ("Fix", "How Pro handles it"),
        "rows": [
            ("Publish / update llms.txt", "auto", "Fully automatic PR"),
            ("Allow AI crawlers in robots.txt", "auto", "Fully automatic PR"),
            ("Publish sitemap.xml", "auto", "Fully automatic PR"),
            ("Insert JSON-LD", "manual", "Recommendation (you place it)"),
            ("Rewrite body copy", "manual", "Recommendation (you decide the wording)"),
        ],
        "set_h": "Option: bundle Kurage URL2GPTResearcher",
        "set_sub": "GEO prepares the <b>ground for being found</b>. But if the content on top has not changed "
                   "in years, the site still reads as one that stopped moving. The publishing itself can be "
                   "bundled into Pro.",
        "set_cols": [
            ("What Kurage GEO Pro does",
             "AI crawler access, llms.txt, structured data, body structure — it prepares the "
             "<b>technical ground for AI to understand and cite you</b>, and repairs it when it regresses."),
            ("What Kurage URL2GPTResearcher does",
             "AI reads what your site is about, then <b>researches related news, writes it up and keeps "
             "publishing</b> on your site. All that sits on your server is one display-only PHP file."),
            ("Bundled",
             "For a site whose audit flags weak update signals, you get the groundwork fixes and the "
             "<b>updates themselves</b> at once — audit, fix and publish become one line."),
        ],
        "set_price": "Bundle pricing on request",
        "set_links": 'Kurage URL2GPTResearcher is <b>available on its own today</b> (\u00a5200 or 20,000 URLAI per research). '
                     '→ <a href="https://kurage.exbridge.jp/kurl2gr.php?lang=en">Start</a> / '
                     '<a href="https://kurl2gr.exbridge.jp/" target="_blank" rel="noopener">About the service</a>',
        "set_note": "* The bundle is a <b>concept</b>, like Kurage GEO Pro itself. Availability is undecided and "
                    "pricing is agreed case by case.",
        "note": "* This section describes a <b>concept</b>. Availability, pricing and features are undecided. "
                "What you can use today is the GEO audit only — first one free, then ¥200 (or 20,000 URLAI) "
                "per audit. No guarantee of search rankings or inclusion in AI answers.",
    },
}


def build(lang: str) -> str:
    t = TEXT[lang]
    items = "\n".join(
        f'      <div class="pro-item"><h3>{head}</h3><p>{body}</p></div>'
        for head, body in t["items"]
    )
    rows = "\n".join(
        f'        <tr><td>{name}</td>'
        f'<td class="pro-{kind}">{label}</td></tr>'
        for name, kind, label in t["rows"]
    )
    cols = "\n".join(
        f'        <div class="set-col"><h4>{head}</h4><p>{body}</p></div>'
        for head, body in t["set_cols"]
    )
    return f"""{BEGIN}
{STYLE}
<section class="pro-sec" id="kurage-geo-pro">
  <div class="pro-box">
    <span class="pro-badge">{t['badge']}</span>
    <h2>{t['h']}</h2>
    <p class="pro-lead">{t['lead']}</p>
    <div class="pro-grid">
{items}
    </div>
    <table class="pro-table">
      <tr><th>{t['table_h'][0]}</th><th>{t['table_h'][1]}</th></tr>
{rows}
    </table>
    <p class="pro-note">{t['note']}</p>
  </div>

  <div class="set-box">
    <h3>{t['set_h']}</h3>
    <p class="set-sub">{t['set_sub']}</p>
    <div class="set-cols">
{cols}
    </div>
    <p><span class="set-price">{t['set_price']}</span></p>
    <p class="set-links">{t['set_links']}</p>
    <p class="pro-note">{t['set_note']}</p>
  </div>
</section>
{END}"""


def build_php() -> str:
    """kgeo.php 用。1ファイルで両言語を持つため $lang で出し分ける。"""
    return (f"{BEGIN}\n{STYLE}\n"
            "<?php if ($lang === 'en'): ?>\n"
            + build("en").replace(BEGIN, "").replace(END, "").replace(STYLE, "").strip()
            + "\n<?php else: ?>\n"
            + build("ja").replace(BEGIN, "").replace(END, "").replace(STYLE, "").strip()
            + f"\n<?php endif; ?>\n{END}")


def main() -> int:
    for lang, path in PAGES.items():
        html = path.read_text(encoding="utf-8")
        block = build(lang)
        if BEGIN in html:
            html = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), block, html, flags=re.S)
            action = "更新"
        else:
            # 料金セクションの直後に置く。「月額なし」の説明の次に
            # 「月額版を構想中」が来る流れが自然。
            marker = "<!-- BEGIN kurage-ecosystem"
            if marker not in html:
                raise SystemExit(f"{path} に挿入位置の目印が見つからない")
            html = html.replace(marker, block + "\n\n" + marker, 1)
            action = "追加"
        path.write_text(html, encoding="utf-8")
        print(f"{action}: {path.name} ({lang})")

    html = PHP_PAGE.read_text(encoding="utf-8")
    block = build_php()
    if BEGIN in html:
        html = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), block, html, flags=re.S)
        action = "更新"
    else:
        marker = "<!-- BEGIN kurage-ecosystem"
        if marker not in html:
            raise SystemExit(f"{PHP_PAGE} に挿入位置の目印が見つからない")
        html = html.replace(marker, block + "\n\n" + marker, 1)
        action = "追加"
    PHP_PAGE.write_text(html, encoding="utf-8")
    print(f"{action}: {PHP_PAGE.name} (ja/en 両方)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
