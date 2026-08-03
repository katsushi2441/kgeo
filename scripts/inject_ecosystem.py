"""kgeo のLPに「Kurageシリーズ紹介」と「URLAIトークン紹介」を差し込む。

kurl2earn / llm2api と同じ2セクションを載せるが、kgeoのLPは配色体系が違う
(--abyss / --foam / --panel / --teal のライト・ダーク両対応)。
そのため意匠はkgeoのトークンに合わせて書き、内容だけを揃えている。

何度実行しても同じ結果になる(既存の差し込みを置き換える)。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = {"ja": ROOT / "landing" / "kgeo.html", "en": ROOT / "landing" / "index.html"}

BEGIN = "<!-- BEGIN kurage-ecosystem (scripts/inject_ecosystem.py が生成) -->"
END = "<!-- END kurage-ecosystem -->"

# (名前, URL, OGP画像, 日本語説明, 英語説明)
PRODUCTS = [
    ("📈 Kurage FreqAI Trade", "https://kfreqai.exbridge.jp/",
     "https://kfreqai.exbridge.jp/assets/ogp.png",
     "自分の負けを自分で研究する、自己改善型の暗号資産AI自動取引。全過程をブログで公開。",
     "Self-improving crypto AI trading that researches its own losses. The whole process is published on the blog."),
    ("🌊 Kurage FreqAI for Hyperliquid", "https://kurage.exbridge.jp/kfreqaihl.php",
     "https://kurage.exbridge.jp/images/kfreqaihl_ogp.png",
     "ウォレット1つ・サーバー不要のAI自動取引。CryptoからFX・金・株価指数まで。",
     "AI auto-trading with one wallet and no server. From crypto to FX, gold and equity indices."),
    ("💱 Kurage FX AI Trade", "https://kfxai.exbridge.jp/",
     "https://kfxai.exbridge.jp/assets/ogp.png",
     "OANDA APIのFX自動運用×差し替え可能なAI判断レイヤー。円ペアをペーパー取引で検証中。",
     "OANDA-API FX automation with a swappable AI judgment layer. Yen pairs are being validated on paper trading."),
    ("🤖 LLM2API", "https://llm2api.exbridge.jp/",
     "https://llm2api.exbridge.jp/assets/ogp.png",
     "エージェントが1回ずつ買えるLLM推論。OpenAI互換をx402の従量課金で提供。",
     "Pay-per-call LLM inference for agents. OpenAI-compatible, billed per request over x402."),
    ("🎙️ Kurage VTuber", "https://kvtuber.exbridge.jp/",
     "https://kvtuber.exbridge.jp/assets/ogp.png",
     "リアルタイムに会話するKurageのAI VTuber。配信・対話のコア。",
     "Kurage's real-time conversational AI VTuber. The core of streaming and dialogue."),
    ("📝 Kurage URL2AI Publisher", "https://url2ai.exbridge.jp/",
     "https://url2ai.exbridge.jp/assets/ogp.png",
     "URLを渡すとKurageさんが記事を読み、告知文とブログを書いて5媒体へ自動配信。",
     "Give it a URL and Kurage reads the page, writes an announcement and a blog post, then publishes to five channels."),
    ("🎬 kmontage", "https://kmontage.exbridge.jp/",
     "https://kmontage.exbridge.jp/assets/ogp.png",
     "台本から動画（モンタージュ）を自動生成する、Kurageの動画制作システム。",
     "Kurage's video production system that generates montages automatically from a script."),
    ("🖱️ Kurage Argo Video（kargov）", "https://github.com/katsushi2441/kargov",
     "https://kurl2earn.exbridge.jp/assets/cards/kargov.png",
     "AIがブラウザを操作した記録から、デモ・マニュアル動画を自動生成する制作パイプライン。",
     "A pipeline that turns recordings of AI browser operations into demo and manual videos."),
    ("🪼 Kurage（総合ポータル）", "https://kurage.exbridge.jp/",
     "https://kurage.exbridge.jp/images/kurage_ogp.png",
     "Kurageシリーズの入口。全プロダクトと紹介動画をまとめたポータル。",
     "The entrance to the Kurage series. All products and intro videos in one place."),
]

TEXT = {
    "ja": {
        "eco_h": "Kurageシリーズ",
        "eco_sub": "Kurage GEO は、Kurageエコシステムのひとつです。",
        "v_h": "URLAIはエコシステムのトークン",
        "v_p": 'URLAIは、<b>Kurageエコシステムを広めるためのトークン</b>です。'
               '<a href="https://kurl2earn.exbridge.jp/kurl2earn.php" target="_blank" rel="noopener">URL2Earn</a>だけでなく、'
               '<b>kfreqaiのアンバサダー</b>にも配布されます。Kurage GEO の診断も 20,000 URLAI で利用できます。',
        "v_l1": "アンバサダーは <b>kfreqai</b> を使って暗号資産・FXをトレードし、その成果を発信します。",
        "v_l2": "それが kfreqai の<b>収益性を高め、認知を広め</b>、やがて<b>たくさんの人の収益につながるプロジェクト</b>を目指しています。",
        "v_l3": "URLAIは、その拡散と貢献に対して配られる、<b>トークノミクスにおけるエコシステムの一部</b>になることを目指しています。",
        "v_fine": '※URLAIは <a href="https://kfreqai.exbridge.jp/kfreqai.html" target="_blank" rel="noopener">Kurage FreqAI</a> '
                  'エコシステムのトークンです。価格や流動性は市場により変動し、金銭的価値を保証するものではありません。',
    },
    "en": {
        "eco_h": "The Kurage series",
        "eco_sub": "Kurage GEO is one product in the Kurage ecosystem.",
        "v_h": "URLAI is the ecosystem token",
        "v_p": 'URLAI is <b>the token for spreading the Kurage ecosystem</b>. Beyond '
               '<a href="https://kurl2earn.exbridge.jp/kurl2earn.php?lang=en" target="_blank" rel="noopener">URL2Earn</a>, '
               'it is distributed to <b>kfreqai ambassadors</b>. A Kurage GEO audit can also be paid with 20,000 URLAI.',
        "v_l1": "Ambassadors trade crypto and FX with <b>kfreqai</b> and share their results.",
        "v_l2": "That <b>improves kfreqai's profitability and spreads awareness</b>, aiming at "
                "<b>a project that eventually earns for many people</b>.",
        "v_l3": "URLAI aims to be <b>part of the ecosystem's tokenomics</b>, distributed for that spreading and contribution.",
        "v_fine": '* URLAI is a token of the <a href="https://kfreqai.exbridge.jp/" target="_blank" rel="noopener">Kurage FreqAI</a> '
                  'ecosystem. Its price and liquidity fluctuate with the market and no monetary value is guaranteed.',
    },
}

# kgeoのトークン(--panel / --teal 等)に合わせる。llm2api側とは配色体系が違うため
# 同じCSSは使い回さず、内容だけを揃えている。
STYLE = """<style>
  .kx-sec { max-width:1080px; margin:0 auto; padding:38px 20px; }
  .kx-h { font-size:clamp(20px,3vw,27px); font-weight:800; text-align:center; margin-bottom:6px; }
  .kx-sub { text-align:center; color:var(--abyss-soft); font-size:14px; margin-bottom:24px; }
  .kx-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(270px,1fr)); gap:16px; }
  .kx-card { display:block; background:var(--panel); border:1px solid var(--panel-line);
    border-radius:16px; overflow:hidden; box-shadow:var(--shadow); transition:transform .15s; }
  .kx-card:hover { transform:translateY(-3px); }
  .kx-card .kx-im { aspect-ratio:1200/630; background:var(--foam); overflow:hidden; }
  .kx-card .kx-im img { width:100%; height:100%; object-fit:cover; display:block; }
  .kx-card .kx-tx { padding:14px 16px 16px; }
  .kx-card .kx-nm { font-weight:800; font-size:15px; color:var(--abyss); }
  .kx-card .kx-ds { font-size:12.5px; color:var(--abyss-soft); margin-top:5px; line-height:1.7; }
  .kx-card .kx-lk { font-size:12px; color:var(--teal-deep); font-weight:700; margin-top:8px; word-break:break-all; }
  .kx-vision { background:var(--gold-bg); border:1px solid var(--gold-line); border-radius:18px; padding:26px; }
  .kx-vision p { font-size:14.5px; }
  .kx-vision ul { padding-left:22px; margin-top:12px; font-size:14px; color:var(--abyss); }
  .kx-vision li { margin-bottom:8px; }
  .kx-vision b { color:var(--gold); }
  .kx-fine { font-size:12px; color:var(--abyss-soft); margin-top:14px; }
</style>"""


def build(lang: str) -> str:
    t = TEXT[lang]
    cards = []
    for name, url, image, ja_desc, en_desc in PRODUCTS:
        desc = ja_desc if lang == "ja" else en_desc
        label = url.replace("https://", "").rstrip("/")
        cards.append(
            f'    <a class="kx-card" href="{url}" target="_blank" rel="noopener">\n'
            f'      <div class="kx-im"><img src="{image}" alt="{name}" loading="lazy"></div>\n'
            f'      <div class="kx-tx"><div class="kx-nm">{name}</div>\n'
            f'        <div class="kx-ds">{desc}</div>\n'
            f'        <div class="kx-lk">{label} →</div></div>\n'
            f'    </a>')
    return f"""{BEGIN}
{STYLE}
<section class="kx-sec" id="kurage-ecosystem">
  <h2 class="kx-h">{t['eco_h']}</h2>
  <p class="kx-sub">{t['eco_sub']}</p>
  <div class="kx-grid">
{chr(10).join(cards)}
  </div>
</section>

<section class="kx-sec" id="urlai">
  <h2 class="kx-h">{t['v_h']}</h2>
  <div class="kx-vision">
    <p>{t['v_p']}</p>
    <ul>
      <li>{t['v_l1']}</li>
      <li>{t['v_l2']}</li>
      <li>{t['v_l3']}</li>
    </ul>
    <p class="kx-fine">{t['v_fine']}</p>
  </div>
</section>
{END}"""


def main() -> int:
    for lang, path in PAGES.items():
        html = path.read_text(encoding="utf-8")
        block = build(lang)
        if BEGIN in html:
            html = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), block, html, flags=re.S)
            action = "更新"
        else:
            if "</main>" not in html:
                raise SystemExit(f"{path} に </main> が見つからない")
            html = html.replace("</main>", f"{block}\n\n</main>", 1)
            action = "追加"
        path.write_text(html, encoding="utf-8")
        print(f"{action}: {path.name} ({lang}) 商材{len(PRODUCTS)}件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
