<?php
require_once __DIR__ . '/config.php';
require_once __DIR__ . '/auth_common.php';
require_once __DIR__ . '/kgeo_config.php';
date_default_timezone_set('Asia/Tokyo');

$THIS_FILE = 'kgeo.php';
if (isset($_GET['login'])) {
    header('Location: ' . url2ai_auth_login_url('/' . $THIS_FILE));
    exit;
}
if (isset($_GET['logout'])) {
    header('Location: ' . url2ai_auth_logout_url('/' . $THIS_FILE));
    exit;
}

$auth = url2ai_auth_bootstrap();
$logged_in = !empty($auth['logged_in']);
$session_user = $logged_in ? trim((string)$auth['session_user']) : '';
if (empty($_SESSION['kgeo_csrf'])) {
    $_SESSION['kgeo_csrf'] = bin2hex(random_bytes(24));
}
$csrf = (string)$_SESSION['kgeo_csrf'];

function kgeo_error($status, $detail) {
    http_response_code((int)$status);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store, max-age=0');
    echo json_encode(array('detail' => $detail), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function kgeo_route_allowed($path, $method) {
    if (in_array($path, array('/health', '/api/usage', '/api/sites'), true)) {
        return ($path === '/api/sites') ? in_array($method, array('GET', 'POST'), true) : $method === 'GET';
    }
    if (preg_match('#^/api/sites/[a-f0-9]{12}$#', $path)) { return $method === 'GET'; }
    if (preg_match('#^/api/sites/[a-f0-9]{12}/audits$#', $path)) { return in_array($method, array('GET', 'POST'), true); }
    if (preg_match('#^/api/sites/[a-f0-9]{12}/prompts$#', $path)) { return in_array($method, array('GET', 'POST'), true); }
    if (preg_match('#^/api/audits/[a-f0-9]{12}$#', $path)) { return $method === 'GET'; }
    if (preg_match('#^/api/prompts/[a-f0-9]{12}/runs$#', $path)) { return in_array($method, array('GET', 'POST'), true); }
    return false;
}

function kgeo_proxy($method, $path, $user) {
    $headers = array(
        'Accept: application/json',
        'Content-Type: application/json',
        'X-KGeo-Token: ' . KGEO_API_TOKEN,
        'X-KGeo-User: ' . $user,
    );
    $ch = curl_init(rtrim(KGEO_API_BASE, '/') . $path);
    curl_setopt_array($ch, array(
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_CONNECTTIMEOUT => 8,
        CURLOPT_TIMEOUT => 180,
        CURLOPT_CUSTOMREQUEST => $method,
        CURLOPT_HTTPHEADER => $headers,
    ));
    if (in_array($method, array('POST', 'PUT'), true)) {
        $raw = file_get_contents('php://input');
        if (strlen($raw) > 100000) { kgeo_error(413, '入力が大きすぎます'); }
        if ($raw !== '') {
            json_decode($raw);
            if (json_last_error() !== JSON_ERROR_NONE) { kgeo_error(400, 'JSONを確認してください'); }
            curl_setopt($ch, CURLOPT_POSTFIELDS, $raw);
        }
    }
    $body = curl_exec($ch);
    $status = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $content_type = (string)curl_getinfo($ch, CURLINFO_CONTENT_TYPE);
    $error = curl_error($ch);
    curl_close($ch);
    if ($body === false || $error !== '') { kgeo_error(502, 'Kurage GEO APIへ接続できません'); }
    http_response_code($status ?: 502);
    header('Content-Type: ' . ($content_type ?: 'application/json; charset=utf-8'));
    header('Cache-Control: no-store, max-age=0');
    echo $body;
    exit;
}

if (isset($_GET['asset'])) {
    $assets = array('styles.css' => 'assets/kgeo.css', 'app.js' => 'assets/kgeo.js');
    $name = (string)$_GET['asset'];
    if (!isset($assets[$name])) { http_response_code(404); exit; }
    $path = realpath(__DIR__ . '/' . $assets[$name]);
    $root = realpath(__DIR__ . '/assets');
    // ローカル開発ツリーではデプロイ用assetsの代わりに../staticを参照する。
    if (!$path || !$root) {
        $fallback = array('styles.css' => '../static/styles.css', 'app.js' => '../static/app.js');
        $path = realpath(__DIR__ . '/' . $fallback[$name]);
        $root = realpath(__DIR__ . '/../static');
    }
    if (!$path || !$root || strpos($path, $root . DIRECTORY_SEPARATOR) !== 0) { http_response_code(404); exit; }
    header('Content-Type: ' . (substr($name, -3) === '.js' ? 'application/javascript; charset=utf-8' : 'text/css; charset=utf-8'));
    header('Cache-Control: public, max-age=3600');
    readfile($path);
    exit;
}

if (isset($_GET['api'])) {
    if (!$logged_in) { kgeo_error(401, 'Xログインが必要です'); }
    $path = rawurldecode((string)$_GET['api']);
    $method = strtoupper((string)($_SERVER['REQUEST_METHOD'] ?? 'GET'));
    if (!kgeo_route_allowed($path, $method)) { kgeo_error(404, 'Unknown route'); }
    if ($method !== 'GET') {
        $sent = (string)($_SERVER['HTTP_X_CSRF_TOKEN'] ?? '');
        if (!$sent || !hash_equals($csrf, $sent)) { kgeo_error(403, 'CSRF検証に失敗しました'); }
    }
    kgeo_proxy($method, $path, $session_user);
}

if (!$logged_in):
?><!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kurage GEO | GEO Optimizer・AiCMOを日本語で使えるGEO診断</title>
<meta name="description" content="OSSのGEO Optimizerを監査中核に、AiCMOの設計を参考に日本語向けへ再構成。GEO技術監査、日本語AEO診断、根拠付きLLM回答シミュレーションを提供します。">
<meta name="keywords" content="GEO Optimizer 日本語,AiCMO 日本語,GEO 日本語,AEO 日本語,回答エンジン最適化,AI検索対策,生成AI SEO,LLMO,Kurage GEO">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="author" content="Kurageプロジェクト">
<meta name="theme-color" content="#0c9bae">
<link rel="canonical" href="https://kurage.exbridge.jp/kgeo.php">
<link rel="alternate" type="text/markdown" href="https://kurage.exbridge.jp/llms.txt" title="Kurage Project for LLMs">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Kurageプロジェクト">
<meta property="og:title" content="Kurage GEO — GEO Optimizer／AiCMOを日本語で活用">
<meta property="og:description" content="GEO技術監査、日本語AEO診断、対象ページを根拠にしたLLM回答シミュレーションを一つの日本語画面で。">
<meta property="og:url" content="https://kurage.exbridge.jp/kgeo.php">
<meta property="og:image" content="https://kurage.exbridge.jp/images/kgeo-ogp.png">
<meta property="og:image:secure_url" content="https://kurage.exbridge.jp/images/kgeo-ogp.png">
<meta property="og:image:type" content="image/png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Kurage GEO — GEO OptimizerとAiCMOを日本語で活用するGEOワークスペース">
<meta property="og:locale" content="ja_JP">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Kurage GEO — GEO Optimizer／AiCMOを日本語で活用">
<meta name="twitter:description" content="GEO技術監査、日本語AEO診断、根拠付きLLM回答シミュレーションを一つの日本語画面で。">
<meta name="twitter:image" content="https://kurage.exbridge.jp/images/kgeo-ogp.png">
<script type="application/ld+json">
{
  "@context":"https://schema.org",
  "@type":"WebApplication",
  "name":"Kurage GEO",
  "alternateName":["日本語GEO・AEO診断ワークスペース","GEO Optimizer・AiCMO日本語GEOツール"],
  "url":"https://kurage.exbridge.jp/kgeo.php",
  "description":"OSSのGEO Optimizerを監査中核に使い、AiCMOの設計を参考に、日本語AEO診断と対象ページを根拠にしたLLM回答シミュレーションを追加したGEOワークスペース。",
  "applicationCategory":"BusinessApplication",
  "operatingSystem":"Web",
  "inLanguage":"ja",
  "isAccessibleForFree":true,
  "image":"https://kurage.exbridge.jp/images/kgeo-ogp.png",
  "codeRepository":"https://github.com/katsushi2441/kgeo",
  "license":"https://opensource.org/license/mit",
  "keywords":"GEO Optimizer 日本語, AiCMO 日本語, GEO, AEO 日本語, 回答エンジン最適化, AI検索対策, LLMO, 生成AI SEO",
  "isBasedOn":[
    {"@type":"SoftwareSourceCode","name":"GEO Optimizer Skill","codeRepository":"https://github.com/Auriti-Labs/geo-optimizer-skill","license":"https://opensource.org/license/mit"},
    {"@type":"SoftwareSourceCode","name":"AiCMO","codeRepository":"https://github.com/AICMO/ai-cmo","license":"https://opensource.org/license/mit"}
  ],
  "featureList":["GEO OptimizerによるGEO技術監査","AIクローラー許可診断","llms.txt診断","構造化データ診断","日本語AEOの独立採点","47項目の引用適性診断","対象ページを根拠にしたLLM回答シミュレーション"],
  "publisher":{"@type":"Organization","name":"Kurageプロジェクト","url":"https://kurage.exbridge.jp/"}
}
</script>
<script type="application/ld+json">
{
  "@context":"https://schema.org",
  "@type":"FAQPage",
  "mainEntity":[
    {"@type":"Question","name":"GEO Optimizerを日本語で使えますか？","acceptedAnswer":{"@type":"Answer","text":"Kurage GEOはGEO Optimizerの決定論的な監査機能を中核に使い、監査結果を日本語画面で確認できます。さらに日本語固有の回答先出し、定義、Q&A、根拠、可読性、検索意図、断定リスクを独立採点します。公式日本語版ではありません。"}},
    {"@type":"Question","name":"AiCMOとの関係は何ですか？","acceptedAnswer":{"@type":"Answer","text":"AiCMOの企業・競合・監視質問・実行履歴・AI可視性という設計を参考に、Kurage GEO独自の軽量な日本語データモデルとして実装しています。AiCMO全体を翻訳した公式版ではありません。"}},
    {"@type":"Question","name":"SEOとGEOの違いは何ですか？","acceptedAnswer":{"@type":"Answer","text":"SEOは主に検索結果での発見性を改善し、GEOは生成AIやAI検索が内容を理解・引用しやすい技術構成と情報表現を整えます。Kurage GEOはrobots.txt、llms.txt、構造化データ、本文構造などを監査します。"}}
  ]
}
</script>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-BP0650KDFR"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}gtag('js',new Date());gtag('config','G-BP0650KDFR');</script>
<script>(function(){var s=document.createElement('script');s.src='https://aiknowledgecms.exbridge.jp/simpletrack.php?url='+encodeURIComponent(location.href)+'&ref='+encodeURIComponent(document.referrer);document.head.appendChild(s)})();</script>
<style>body{margin:0;background:#f5fcfd;color:#15334a;font-family:-apple-system,BlinkMacSystemFont,"Noto Sans JP",sans-serif}.wrap{max-width:900px;margin:7vh auto;padding:28px}.card,.feature,.oss,.faq details{background:#fff;border:1px solid #dce8ee;border-radius:28px;box-shadow:0 18px 55px rgba(24,75,99,.1)}.card{padding:48px;text-align:center}.mark{width:70px;height:70px;margin:auto;display:grid;place-items:center;border-radius:22px;background:#0c9bae;color:#fff;font-size:36px;font-weight:900}h1{font-size:38px;margin:20px 0 10px}p{color:#667b8b;line-height:1.8}.button{display:inline-flex;min-height:50px;align-items:center;margin-top:18px;padding:0 28px;border-radius:14px;background:#0c9bae;color:#fff;text-decoration:none;font-weight:800}.about{text-align:center;margin:48px auto 22px;max-width:760px}.about h2,.oss h2,.faq h2{font-size:26px;margin:0 0 8px}.features{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.feature{padding:22px;border-radius:18px;box-shadow:0 10px 28px rgba(24,75,99,.06)}.feature h3{font-size:16px;margin:0 0 7px;color:#087988}.feature p{font-size:13px;margin:0}.oss{padding:28px;margin-top:28px;border-radius:20px}.oss a{color:#087988;font-weight:700}.oss .note{font-size:12px}.faq{margin-top:40px}.faq h2{text-align:center}.faq details{padding:17px 20px;margin-top:11px;border-radius:16px;box-shadow:0 8px 22px rgba(24,75,99,.05)}.faq summary{cursor:pointer;font-weight:800;color:#087988}.faq details p{font-size:13px;margin:8px 0 0}.foot{text-align:center;font-size:12px;margin:26px 0 0}@media(max-width:700px){.wrap{margin:3vh auto;padding:18px}.card{padding:36px 22px}.features{grid-template-columns:1fr}}</style></head><body><main class="wrap"><section class="card"><div class="mark">G</div><h1>Kurage GEO</h1><p>GEO OptimizerとAiCMOの知見を、日本語で使えるGEO監査・AI検索可視性ワークスペースへ。<br>利用には共通Xアカウントでのログインが必要です。</p><a class="button" href="?login=1">Xでログイン</a></section><section class="about"><h2>GEO Optimizer／AiCMOを日本語で活用</h2><p>OSSの<strong>GEO Optimizer</strong>を技術監査の中核に使い、<strong>AiCMO</strong>のAI可視性・競合・監視質問・履歴という設計を参考に、日本語で理解しやすい一つのWebプロダクトへ再構成しました。</p></section><section class="features" aria-label="Kurage GEOの機能"><article class="feature"><h3>AIクローラーとllms.txt</h3><p>robots.txtの許可状況、llms.txt、AI向け発見エンドポイントを確認します。</p></article><article class="feature"><h3>構造化データと引用適性</h3><p>JSON-LD、メタ情報、本文構造、更新シグナル、ブランド表記の整合性を監査します。</p></article><article class="feature"><h3>履歴とAI検索可視性</h3><p>監査結果を保存し、対応前後の変化やAI回答でのブランド言及・URL引用を記録します。</p></article></section><section class="oss"><h2>2つのOSSとの関係</h2><p><a href="https://github.com/Auriti-Labs/geo-optimizer-skill" rel="noopener">GEO Optimizer Skill</a>の安全なURL取得と決定論的監査を実際の監査エンジンとして利用しています。<a href="https://github.com/AICMO/ai-cmo" rel="noopener">AiCMO</a>は、企業・競合・監視質問・実行履歴というプロダクト設計の参照元です。</p><p class="note">Kurage GEOは両OSSの公式日本語版ではなく、MIT Licenseに基づく独立した日本語プロダクトです。AiCMO全体をそのまま翻訳したものではありません。</p></section><section class="faq"><h2>GEO Optimizer・AiCMO 日本語対応FAQ</h2><details open><summary>GEO Optimizerを日本語で使えますか？</summary><p>Kurage GEOでは監査結果と改善案を日本語画面で確認できます。GEO Optimizerの公式日本語版ではありません。</p></details><details><summary>AiCMOとの関係は何ですか？</summary><p>AiCMOのAI可視性モニタリング設計を参考に、Kurage GEO独自の軽量な日本語データモデルとして実装しています。</p></details><details><summary>SEOとGEOの違いは何ですか？</summary><p>SEOは主に検索結果での発見性を改善し、GEOは生成AIやAI検索が内容を理解・引用しやすい技術構成と情報表現を整えます。</p></details></section><p class="foot">Kurage GEOは検索順位やAI回答への掲載を保証するものではありません。観測事実と改善判断を支援するツールです。</p></main></body></html><?php
exit;
endif;

$html_path = file_exists(__DIR__ . '/kgeo_app.html')
    ? __DIR__ . '/kgeo_app.html'
    : __DIR__ . '/../static/index.html';
$html = file_get_contents($html_path);
$html = str_replace('href="/static/styles.css"', 'href="?asset=styles.css"', $html);
$html = str_replace('src="/static/app.js" defer', 'src="?asset=app.js" defer', $html);
$bootstrap = '<script>window.KGEO_API_PREFIX="?api=";window.KGEO_CSRF=' . json_encode($csrf) . ';</script>'
    . '<script async src="https://www.googletagmanager.com/gtag/js?id=G-BP0650KDFR"></script>'
    . '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}gtag("js",new Date());gtag("config","G-BP0650KDFR");</script>'
    . '<script>(function(){var s=document.createElement("script");s.src="https://aiknowledgecms.exbridge.jp/simpletrack.php?url="+encodeURIComponent(location.href)+"&ref="+encodeURIComponent(document.referrer);document.head.appendChild(s)})();</script>';
$html = str_replace('</head>', $bootstrap . '</head>', $html);
echo $html;
