# Third-party software

## GEO Optimizer Skill

- Upstream: https://github.com/Auriti-Labs/geo-optimizer-skill
- Pinned commit: `68f420b6b8ac0079f150be0bcfd78a8eee6808a2`
- License: MIT
- Role: deterministic GEO audit, URL validation, SSRF-resistant fetching

## AiCMO

- Upstream: https://github.com/AICMO/ai-cmo
- Pinned commit: `fc407efaf013b19bdf534357b144f86a5ad714d1`
- License: MIT
- Role: reference architecture for companies, competitors, monitored prompts, prompt runs, visibility metrics

## next-forge (`packages/seo`)

- Upstream: https://github.com/vercel/next-forge
- License: MIT
- Role: `app/seo.py` として移植。JSON-LDを `<script>` へ埋め込む際のエスケープ
  (`escapeJsonForHtml`) と、OGP・Twitter Card などメタ情報の組み立て
  (`createMetadata`) の2点。TypeScript/Next.js版をPythonへ書き直したもので、
  コードのコピーではなく処理の移植です。

Kurage GEOの独自コードは上記プロジェクトを装っておらず、各名称とライセンスを明記して利用します。
