<?php
require_once __DIR__ . '/config.php';
require_once __DIR__ . '/auth_common.php';
require_once __DIR__ . '/kgeo_config.php';
require_once __DIR__ . '/kgeo_billing.php';
date_default_timezone_set('Asia/Tokyo');

$THIS_FILE = 'kgeo.php';

// 言語判定: ?lang=en/ja で切替＆Cookieに保存。以降はCookieで維持（url2pubと同方式）。
$lang = 'ja';
if (isset($_GET['lang'])) {
    $lang = ($_GET['lang'] === 'en') ? 'en' : 'ja';
    setcookie('kgeo_lang', $lang, time() + 31536000, '/');
    $_COOKIE['kgeo_lang'] = $lang;
} elseif (isset($_COOKIE['kgeo_lang']) && $_COOKIE['kgeo_lang'] === 'en') {
    $lang = 'en';
}

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
$is_admin = $logged_in && !empty($auth['is_admin']);
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
    if ($path === '/billing/status') { return $method === 'GET'; }
    if (in_array($path, array('/billing/paypal', '/billing/urlai'), true)) { return $method === 'POST'; }
    if (in_array($path, array('/health', '/api/usage', '/api/sites'), true)) {
        return ($path === '/api/sites') ? in_array($method, array('GET', 'POST'), true) : $method === 'GET';
    }
    if (preg_match('#^/api/sites/[a-f0-9]{12}$#', $path)) { return $method === 'GET'; }
    if (preg_match('#^/api/sites/[a-f0-9]{12}/audits$#', $path)) { return in_array($method, array('GET', 'POST'), true); }
    if (preg_match('#^/api/sites/[a-f0-9]{12}/prompts$#', $path)) { return in_array($method, array('GET', 'POST'), true); }
    if (preg_match('#^/api/audits/[a-f0-9]{12}$#', $path)) { return $method === 'GET'; }
    // 監査レポートのダウンロード。lang だけはクエリを許す(値も ja|en に限定する)。
    if (preg_match('#^/api/audits/[a-f0-9]{12}/report\.(md|pdf)(\?lang=(ja|en))?$#', $path)) {
        return $method === 'GET';
    }
    if (preg_match('#^/api/prompts/[a-f0-9]{12}/runs$#', $path)) { return in_array($method, array('GET', 'POST'), true); }
    return false;
}

function kgeo_backend_get($path, $user) {
    $ch = curl_init(rtrim(KGEO_API_BASE, '/') . $path);
    curl_setopt_array($ch, array(
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_CONNECTTIMEOUT => 8,
        CURLOPT_TIMEOUT => 30,
        CURLOPT_HTTPHEADER => array(
            'Accept: application/json',
            'X-KGeo-Token: ' . KGEO_API_TOKEN,
            'X-KGeo-User: ' . $user,
        ),
    ));
    $body = curl_exec($ch);
    $status = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    return array($status, json_decode((string)$body, true));
}

function kgeo_backend_audit_count($user) {
    list($status, $sites) = kgeo_backend_get('/api/sites', $user);
    if ($status !== 200 || !is_array($sites)) { return null; }
    $count = 0;
    foreach ($sites as $site) {
        $site_id = isset($site['id']) ? (string)$site['id'] : '';
        if (!preg_match('/^[a-f0-9]{12}$/', $site_id)) { continue; }
        list($audit_status, $audits) = kgeo_backend_get('/api/sites/' . $site_id . '/audits', $user);
        if ($audit_status !== 200 || !is_array($audits)) { return null; }
        $count += count($audits);
    }
    return $count;
}

function kgeo_proxy($method, $path, $user, $billing_mode = null) {
    @set_time_limit(650);
    $headers = array(
        'Accept: application/json',
        'Content-Type: application/json',
        'X-KGeo-Token: ' . KGEO_API_TOKEN,
        'X-KGeo-User: ' . $user,
    );
    $ch = curl_init(rtrim(KGEO_API_BASE, '/') . $path);
    // レポートDLはファイル名をバックエンドが決めるので Content-Disposition を転送する。
    // これが無いとブラウザが kgeo.php という名前で保存してしまう。
    $disposition = '';
    curl_setopt_array($ch, array(
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_CONNECTTIMEOUT => 8,
        CURLOPT_TIMEOUT => 620,
        CURLOPT_CUSTOMREQUEST => $method,
        CURLOPT_HTTPHEADER => $headers,
        CURLOPT_HEADERFUNCTION => function ($ch, $line) use (&$disposition) {
            if (stripos($line, 'Content-Disposition:') === 0) {
                $value = trim(substr($line, strlen('Content-Disposition:')));
                // 改行注入を防ぐため制御文字を落とし、想定する形だけ通す。
                $value = preg_replace('/[\x00-\x1F\x7F]/', '', $value);
                if (preg_match('/^attachment; filename="[A-Za-z0-9._-]{1,120}"$/', $value)) {
                    $disposition = $value;
                }
            }
            return strlen($line);
        },
    ));
    if (in_array($method, array('POST', 'PUT'), true)) {
        $raw = file_get_contents('php://input');
        if (strlen($raw) > 100000) { kgeo_error(413, '入力が大きすぎます'); }
        if ($raw !== '') {
            json_decode($raw);
            if (json_last_error() !== JSON_ERROR_NONE) { kgeo_error(400, 'JSONを確認してください'); }
        }
        // 空ボディでもPOSTFIELDSを設定する。未設定だとcurlがContent-Lengthを送らず、
        // Cloud Runのフロントエンドが411 Length Requiredで拒否する（監査・質問実行は空ボディ）。
        curl_setopt($ch, CURLOPT_POSTFIELDS, $raw);
    }
    $body = curl_exec($ch);
    $status = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $content_type = (string)curl_getinfo($ch, CURLINFO_CONTENT_TYPE);
    $error = curl_error($ch);
    curl_close($ch);
    if ($body === false || $error !== '') { kgeo_error(502, 'Kurage GEO APIへ接続できません'); }
    // 無料枠の確定またはクレジット消費は、診断が成功した場合だけ行う。
    if ($billing_mode !== null && $status >= 200 && $status < 300) {
        kgeo_bill_commit($user, $billing_mode);
    }
    http_response_code($status ?: 502);
    header('Content-Type: ' . ($content_type ?: 'application/json; charset=utf-8'));
    header('Cache-Control: no-store, max-age=0');
    if ($disposition !== '') { header('Content-Disposition: ' . $disposition); }
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
    if (!$logged_in || $session_user === '') { kgeo_error(401, 'Xログインが必要です'); }
    if (strlen($session_user) > 200 || preg_match('/[\x00-\x1F\x7F]/', $session_user)) {
        kgeo_error(401, 'ログイン情報を確認できません');
    }
    $path = rawurldecode((string)$_GET['api']);
    $method = strtoupper((string)($_SERVER['REQUEST_METHOD'] ?? 'GET'));
    if (!kgeo_route_allowed($path, $method)) { kgeo_error(404, 'Unknown route'); }
    if ($method !== 'GET') {
        $sent = (string)($_SERVER['HTTP_X_CSRF_TOKEN'] ?? '');
        if (!$sent || !hash_equals($csrf, $sent)) { kgeo_error(403, 'CSRF検証に失敗しました'); }
    }
    if ($path === '/billing/status') {
        // 管理者(xb_bittensor)は課金対象外。バックエンドの監査数集計も省略する。
        $audit_count = $is_admin ? 0 : kgeo_backend_audit_count($session_user);
        if ($audit_count === null) { kgeo_error(502, 'Kurage GEO APIへ接続できません'); }
        header('Content-Type: application/json; charset=utf-8');
        header('Cache-Control: no-store, max-age=0');
        echo json_encode(array(
            'audits' => $audit_count,
            'first_free' => (!$is_admin && $audit_count === 0),
            'credits' => kgeo_bill_credits($session_user),
            'admin_bypass' => $is_admin,
            'price_jpy' => KGEO_PRICE_JPY,
            'price_urlai' => KGEO_PRICE_URLAI,
            'urlai_receiver' => KGEO_URLAI_RECEIVER,
            'paypal_client_id' => KGEO_PAYPAL_CLIENT_ID,
        ), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        exit;
    }
    if (in_array($path, array('/billing/paypal', '/billing/urlai'), true)) {
        $input = json_decode((string)file_get_contents('php://input'), true);
        if (!is_array($input)) { kgeo_error(400, 'JSONを確認してください'); }
        if ($path === '/billing/paypal') {
            list($ok, $message) = kgeo_bill_grant_paypal(
                $session_user,
                isset($input['order_id']) ? $input['order_id'] : ''
            );
        } else {
            list($ok, $message) = kgeo_bill_grant_urlai(
                $session_user,
                isset($input['wallet']) ? $input['wallet'] : ''
            );
        }
        header('Content-Type: application/json; charset=utf-8');
        header('Cache-Control: no-store, max-age=0');
        echo json_encode(array(
            'ok' => $ok,
            'message' => $message,
            'credits' => kgeo_bill_credits($session_user),
        ), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        exit;
    }
    if ($method === 'POST' && preg_match('#^/api/sites/[a-f0-9]{12}/audits$#', $path)) {
        // 管理者(xb_bittensor)は課金ゲートを通さず無料で実行する。
        if ($is_admin) { kgeo_proxy($method, $path, $session_user); }
        $audit_count = kgeo_backend_audit_count($session_user);
        if ($audit_count === null) { kgeo_error(502, 'Kurage GEO APIへ接続できません'); }
        $gate = kgeo_bill_gate($session_user, $audit_count);
        if ($gate === 'need_payment') { kgeo_error(402, 'PAYMENT_REQUIRED'); }
        kgeo_proxy($method, $path, $session_user, $gate);
    }
    kgeo_proxy($method, $path, $session_user);
}

// UI文言（日本語 / English）。ロジックは1本、文言だけ差し替える（url2pubと同方式）。
$T_ALL = array(
'ja' => array(
  'title' => 'Kurage GEO | GEO Optimizer・AiCMOを日本語で使えるGEO診断',
  'meta_desc' => 'OSSのGEO Optimizerを監査中核に、AiCMOの設計を参考に日本語向けへ再構成。初回無料、2回目以降は1診断200円または20,000 URLAIで、GEO技術監査、日本語AEO診断を提供します。',
  'og_locale' => 'ja_JP',
  'brand_sub' => 'AI検索対応(GEO)診断ワークスペース',
  'nav_login' => '𝕏 でログイン',
  'nav_about' => 'Kurage GEOについて',
  'eyebrow' => 'GEO ・ AI検索最適化',
  'h1' => 'AI検索に、<em>見つけてもらえるサイトへ。</em>',
  'lead' => '<b>Kurage GEO</b> は、あなたのサイトが <b>ChatGPTやAI検索に理解・引用されやすいか</b> を日本語で診断するワークスペース。GEO技術監査・日本語AEO採点・対象ページを根拠にした<b>LLM回答シミュレーション</b>で、点数だけで終わらず「次に直す箇所」と判定根拠を示します。',
  'cta_login' => '𝕏 でログインして無料で診断',
  'cta_note' => '共通Xアカウントでログインするだけ。初回診断は無料です。',
  'hero_name' => 'Kurageさん',
  'hero_desc' => 'エクスブリッジのクラゲAI VTuber。あなたのサイトのAI検索対応を診断します。',
  'feat_title' => '診断でわかること',
  'feat_sub' => 'AI検索に「見つけてもらう」ための4つの視点。',
  'chip1' => 'AIクローラー対応', 'chip1s' => 'robots.txt / llms.txt / AI発見性',
  'chip2' => '構造化データ', 'chip2s' => 'JSON-LD・メタ情報・ブランド整合性',
  'chip3' => '日本語AEO', 'chip3s' => '回答エンジンに答えられる本文か',
  'chip4' => '47項目の引用適性', 'chip4s' => 'RAG分割・文脈効率・信頼性',
  'price_title' => '料金 — 初回無料、月額なし',
  'price_sub' => '必要なときに、必要な分だけ。',
  'price1' => 'Xアカウントごとに<b>初回のGEO診断は無料</b>。',
  'price2' => '2回目以降は <b>1診断200円</b> または <b>20,000 URLAI</b>。',
  'price3' => 'PayPal決済とBase上のURLAI送金に対応。<b>成功した診断だけ</b>クレジットを消費。',
  'price4' => '月額契約なし。購入したクレジットに有効期限はありません。',
  'oss_title' => '2つのOSSの上に',
  'oss_p' => '<a href="https://github.com/Auriti-Labs/geo-optimizer-skill" target="_blank" rel="noopener">GEO Optimizer Skill</a> の安全なURL取得と決定論的監査を実際の監査エンジンとして利用し、<a href="https://github.com/AICMO/ai-cmo" target="_blank" rel="noopener">AiCMO</a> のAI可視性・競合・監視質問・実行履歴という設計を参考にしています。',
  'oss_note' => 'Kurage GEOは両OSSの公式日本語版ではなく、MIT Licenseに基づく独立した日本語プロダクトです。検索順位やAI回答への掲載を保証するものではありません。',
  'faq_title' => 'よくある質問',
  'faq1_q' => 'SEOとGEOの違いは何ですか？',
  'faq1_a' => 'SEOは主に検索結果での発見性を改善し、GEOは生成AIやAI検索が内容を理解・引用しやすい技術構成と情報表現を整えます。Kurage GEOはrobots.txt、llms.txt、構造化データ、本文構造などを監査します。',
  'faq2_q' => '診断料金はいくらですか？',
  'faq2_a' => 'Xアカウントごとに初回診断は無料です。2回目以降は1診断200円、または20,000 URLAIで購入した診断クレジットを使います。月額契約はありません。',
  'faq3_q' => 'GEO Optimizer・AiCMOとの関係は？',
  'faq3_a' => 'GEO Optimizerの決定論的な監査機能を中核に使い、AiCMOのAI可視性モニタリング設計を参考にした、MIT Licenseに基づく独立した日本語プロダクトです。公式日本語版ではありません。',
  'footer_product' => '株式会社エクスブリッジのプロダクト',
  'footer_contact' => 'お問い合わせ',
),
'en' => array(
  'title' => 'Kurage GEO | GEO audit workspace for AI search readiness',
  'meta_desc' => 'Kurage GEO audits how ready your website is for AI search (GEO): technical GEO audit, Japanese AEO scoring, and grounded LLM answer simulation. First audit free, then ¥200 or 20,000 URLAI per audit.',
  'og_locale' => 'en_US',
  'brand_sub' => 'AI search readiness (GEO) workspace',
  'nav_login' => 'Sign in with 𝕏',
  'nav_about' => 'About Kurage GEO',
  'eyebrow' => 'GEO ・ AI search optimization',
  'h1' => 'Get your site <em>found by AI search.</em>',
  'lead' => '<b>Kurage GEO</b> is a workspace that audits how <b>easily ChatGPT and AI search can understand and cite your website</b>. A technical GEO audit, Japanese AEO scoring, and a <b>grounded LLM answer simulation</b> tell you not just a score, but what to fix next — with the evidence behind every judgement.',
  'cta_login' => 'Sign in with 𝕏 — first audit free',
  'cta_note' => 'Just sign in with your X account. Your first audit is free.',
  'hero_name' => 'Kurage',
  'hero_desc' => 'EXBRIDGE\'s jellyfish AI VTuber. Audits how AI-search-ready your website is.',
  'feat_title' => 'What the audit tells you',
  'feat_sub' => 'Four angles on being found by AI search.',
  'chip1' => 'AI crawler readiness', 'chip1s' => 'robots.txt / llms.txt / AI discovery',
  'chip2' => 'Structured data', 'chip2s' => 'JSON-LD, meta info, brand consistency',
  'chip3' => 'Japanese AEO', 'chip3s' => 'Can your content answer questions?',
  'chip4' => '47-item citability', 'chip4s' => 'RAG chunking, context efficiency, trust',
  'price_title' => 'Pricing — first audit free, no subscription',
  'price_sub' => 'Pay only for what you use.',
  'price1' => 'The <b>first GEO audit is free</b> for each X account.',
  'price2' => 'From the second audit: <b>¥200</b> or <b>20,000 URLAI</b> per audit.',
  'price3' => 'PayPal and URLAI (on Base) supported. Credits are consumed <b>only when an audit succeeds</b>.',
  'price4' => 'No subscription. Purchased credits never expire.',
  'oss_title' => 'Built on two open-source projects',
  'oss_p' => 'Kurage GEO uses the safe URL fetching and deterministic audits of <a href="https://github.com/Auriti-Labs/geo-optimizer-skill" target="_blank" rel="noopener">GEO Optimizer Skill</a> as its audit engine, and references the AI-visibility product design of <a href="https://github.com/AICMO/ai-cmo" target="_blank" rel="noopener">AiCMO</a>.',
  'oss_note' => 'Kurage GEO is an independent Japanese-focused product under the MIT License — not an official localized version of either project. It does not guarantee rankings or inclusion in AI answers.',
  'faq_title' => 'FAQ',
  'faq1_q' => 'What is the difference between SEO and GEO?',
  'faq1_a' => 'SEO mainly improves discoverability in search results, while GEO prepares the technical structure and information design so generative AI and AI search can understand and cite your content. Kurage GEO audits robots.txt, llms.txt, structured data, content structure, and more.',
  'faq2_q' => 'How much does an audit cost?',
  'faq2_a' => 'The first audit is free for each X account. From the second audit onward, each audit costs ¥200, or one credit purchased with 20,000 URLAI. There is no subscription.',
  'faq3_q' => 'How is it related to GEO Optimizer and AiCMO?',
  'faq3_a' => 'It uses the deterministic audit engine of GEO Optimizer Skill and references the AI-visibility monitoring design of AiCMO, as an independent Japanese-focused product under the MIT License. It is not an official localized version.',
  'footer_product' => 'A product of EXBRIDGE, Inc.',
  'footer_contact' => 'Contact',
),
);
$T = $T_ALL[$lang];

if (!$logged_in):
?><!doctype html><html lang="<?php echo $lang; ?>"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title><?php echo htmlspecialchars($T['title'], ENT_QUOTES, 'UTF-8'); ?></title>
<meta name="description" content="<?php echo htmlspecialchars($T['meta_desc'], ENT_QUOTES, 'UTF-8'); ?>">
<meta name="keywords" content="GEO Optimizer 日本語,AiCMO 日本語,GEO 日本語,AEO 日本語,回答エンジン最適化,AI検索対策,生成AI SEO,LLMO,Kurage GEO">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="author" content="Kurageプロジェクト">
<meta name="theme-color" content="#0c9bae">
<link rel="canonical" href="https://kurage.exbridge.jp/kgeo.php">
<link rel="alternate" hreflang="ja" href="https://kurage.exbridge.jp/kgeo.php?lang=ja">
<link rel="alternate" hreflang="en" href="https://kurage.exbridge.jp/kgeo.php?lang=en">
<link rel="alternate" type="text/markdown" href="https://kurage.exbridge.jp/llms.txt" title="Kurage Project for LLMs">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Kurageプロジェクト">
<meta property="og:title" content="<?php echo htmlspecialchars($T['title'], ENT_QUOTES, 'UTF-8'); ?>">
<meta property="og:description" content="<?php echo htmlspecialchars($T['meta_desc'], ENT_QUOTES, 'UTF-8'); ?>">
<meta property="og:url" content="https://kurage.exbridge.jp/kgeo.php">
<meta property="og:image" content="https://kurage.exbridge.jp/images/kgeo-ogp.png">
<meta property="og:image:secure_url" content="https://kurage.exbridge.jp/images/kgeo-ogp.png">
<meta property="og:image:type" content="image/png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Kurage GEO">
<meta property="og:locale" content="<?php echo $T['og_locale']; ?>">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="<?php echo htmlspecialchars($T['title'], ENT_QUOTES, 'UTF-8'); ?>">
<meta name="twitter:description" content="<?php echo htmlspecialchars($T['meta_desc'], ENT_QUOTES, 'UTF-8'); ?>">
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
  "offers":[
    {"@type":"Offer","name":"初回GEO診断","price":"0","priceCurrency":"JPY","description":"Xアカウントごとに最初の診断は無料"},
    {"@type":"Offer","name":"GEO診断クレジット","price":"200","priceCurrency":"JPY","description":"2回目以降のGEO診断1回。20,000 URLAIでも購入可能"}
  ],
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
    {"@type":"Question","name":"SEOとGEOの違いは何ですか？","acceptedAnswer":{"@type":"Answer","text":"SEOは主に検索結果での発見性を改善し、GEOは生成AIやAI検索が内容を理解・引用しやすい技術構成と情報表現を整えます。Kurage GEOはrobots.txt、llms.txt、構造化データ、本文構造などを監査します。"}},
    {"@type":"Question","name":"Kurage GEOの診断料金はいくらですか？","acceptedAnswer":{"@type":"Answer","text":"Xアカウントごとに初回診断は無料です。2回目以降は1診断200円、または20,000 URLAIで購入した診断クレジットを使います。月額契約はありません。"}}
  ]
}
</script>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-BP0650KDFR"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}gtag('js',new Date());gtag('config','G-BP0650KDFR');</script>
<script>(function(){var s=document.createElement('script');s.src='https://aiknowledgecms.exbridge.jp/simpletrack.php?url='+encodeURIComponent(location.href)+'&ref='+encodeURIComponent(document.referrer);document.head.appendChild(s)})();</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Zen+Maru+Gothic:wght@700;900&family=Zen+Kaku+Gothic+New:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root {
  --abyss:#12202f; --abyss-soft:#55697a; --foam:#f5fbfb; --panel:#e7f3f2; --panel-line:#cde5e2;
  --teal:#12a99f; --teal-deep:#0a726b; --gold:#c98a1e; --gold-bg:#fbf2db; --gold-line:#ecd9a8;
  --shadow:0 14px 40px rgba(10,40,45,.10);
}
@media (prefers-color-scheme:dark){:root{
  --abyss:#eaf3f3; --abyss-soft:#9fb3ba; --foam:#0c1720; --panel:#12242a; --panel-line:#1f3a3f;
  --teal:#2bd4c6; --teal-deep:#1c9e93; --gold:#f2c766; --gold-bg:#241b08; --gold-line:#4c3c17;
  --shadow:0 14px 40px rgba(0,0,0,.38);
}}
* { box-sizing:border-box; margin:0; padding:0; }
html { scroll-behavior:smooth; }
body { color:var(--abyss); font-family:"Zen Kaku Gothic New","Hiragino Sans","Yu Gothic",Meiryo,sans-serif; background:var(--foam); min-height:100vh; line-height:1.8; overflow-x:hidden; }
a { color:var(--teal-deep); text-decoration:none; }
a:hover { color:var(--teal); }
img { max-width:100%; }
h1,h2,h3 { font-family:"Zen Maru Gothic","Zen Kaku Gothic New",sans-serif; text-wrap:balance; }
.wrap { max-width:1000px; margin:0 auto; padding:0 24px; }
header.site { position:sticky; top:0; z-index:40; background:color-mix(in srgb,var(--foam) 88%,transparent); backdrop-filter:blur(16px); border-bottom:1px solid var(--panel-line); }
header.site .wrap { display:flex; align-items:center; gap:12px; padding:12px 24px; flex-wrap:wrap; }
.hbrand { display:flex; gap:12px; align-items:center; }
.hbrand .ico { width:40px; height:40px; border-radius:50%; overflow:hidden; border:2px solid var(--teal); flex:none; }
.hbrand .ico img { width:100%; height:100%; object-fit:cover; object-position:50% 15%; display:block; }
.hbrand strong { font-size:15px; font-weight:900; display:block; line-height:1.2; }
.hbrand span { font-size:11px; color:var(--abyss-soft); }
.hnav { display:flex; gap:8px; align-items:center; margin-left:auto; flex-wrap:wrap; }
.langswitch { display:inline-flex; border:1.5px solid var(--panel-line); border-radius:999px; overflow:hidden; }
.langswitch a { padding:6px 12px; font-size:12px; font-weight:800; color:var(--abyss-soft); }
.langswitch a.on { background:var(--teal); color:#fff; }
.btn { border-radius:999px; padding:10px 18px; font-weight:900; font-size:13px; display:inline-flex; align-items:center; gap:7px; border:1.5px solid transparent; cursor:pointer; text-decoration:none; }
.btn-primary { background:linear-gradient(135deg,var(--teal),var(--teal-deep)); color:#fff; box-shadow:0 10px 24px rgba(18,169,159,.28); }
.btn-ghost { background:transparent; border-color:var(--panel-line); color:var(--abyss-soft); }
.btn-ghost:hover { border-color:var(--teal); color:var(--teal-deep); }
.hero { display:grid; grid-template-columns:1.25fr .75fr; gap:40px; align-items:center; padding:56px 0 34px; }
.eyebrow { display:inline-flex; align-items:center; gap:8px; background:var(--panel); border:1.5px solid var(--panel-line); border-radius:999px; padding:7px 14px; font-size:12px; font-weight:900; color:var(--teal-deep); margin-bottom:18px; }
.dot { width:7px; height:7px; border-radius:50%; background:var(--teal); }
h1 { font-size:clamp(26px,4.4vw,42px); font-weight:900; line-height:1.3; letter-spacing:-.01em; margin-bottom:16px; }
h1 em { font-style:normal; color:var(--teal-deep); }
.lead { font-size:15.5px; color:var(--abyss-soft); max-width:600px; margin-bottom:24px; }
.lead b { color:var(--abyss); }
.cta-row { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
.cta-note { font-size:12px; color:var(--abyss-soft); }
.hero-card { background:var(--panel); border:1.5px solid var(--panel-line); border-radius:28px; padding:24px; text-align:center; box-shadow:var(--shadow); }
.hero-card img { width:180px; height:180px; object-fit:cover; object-position:50% 8%; border-radius:22px; }
.hero-card h2 { font-size:15px; margin:14px 0 4px; }
.hero-card p { font-size:12.5px; color:var(--abyss-soft); }
section { padding:34px 0; }
section > h2 { font-size:clamp(20px,3vw,27px); font-weight:900; margin-bottom:6px; }
section > .sub { color:var(--abyss-soft); font-size:14px; font-weight:700; margin-bottom:24px; }
.chips { display:flex; flex-wrap:wrap; gap:10px; }
.chip { background:var(--panel); border:1.5px solid var(--panel-line); border-radius:14px; padding:14px 18px; font-weight:700; font-size:14px; }
.chip span { display:block; font-size:12px; color:var(--abyss-soft); font-weight:500; margin-top:3px; }
.gate { background:var(--gold-bg); border:1.5px solid var(--gold-line); border-radius:24px; padding:28px; box-shadow:var(--shadow); }
.gate h2 { color:var(--gold); }
.gate ul { list-style:none; margin-top:14px; display:grid; gap:10px; }
.gate li { font-size:14px; padding-left:26px; position:relative; }
.gate li::before { content:"✓"; position:absolute; left:0; color:var(--gold); font-weight:900; }
.oss-note { background:var(--foam); border:1.5px solid var(--panel-line); border-radius:24px; padding:28px; box-shadow:var(--shadow); }
.oss-note p { font-size:14px; color:var(--abyss-soft); margin-top:10px; }
.oss-note a { font-weight:800; color:var(--teal-deep); }
.oss-note small { display:block; margin-top:10px; font-size:12px; color:var(--abyss-soft); }
.faq details { background:var(--foam); border:1.5px solid var(--panel-line); border-radius:16px; padding:16px 20px; margin-top:10px; box-shadow:var(--shadow); }
.faq summary { cursor:pointer; font-weight:800; color:var(--teal-deep); }
.faq details p { font-size:13px; color:var(--abyss-soft); margin:8px 0 0; }
footer.site { text-align:center; color:var(--abyss-soft); font-size:12.5px; padding:44px 20px 54px; border-top:1px solid var(--panel-line); margin-top:24px; }
footer.site a { font-weight:700; }
@media (max-width:760px){ header.site .wrap{ padding:10px 16px; } .wrap{ padding:0 16px; } .hero{ grid-template-columns:1fr; gap:20px; } .hero-card{ order:-1; } .hero-card img{ width:120px; height:120px; } }
</style></head><body>

<header class="site"><div class="wrap">
  <a class="hbrand" href="<?php echo $THIS_FILE; ?>">
    <span class="ico"><img src="images/kurage_avatar_face.webp" alt="Kurage"></span>
    <div><strong>Kurage GEO</strong><span><?php echo htmlspecialchars($T['brand_sub'], ENT_QUOTES, 'UTF-8'); ?></span></div>
  </a>
  <nav class="hnav">
    <div class="langswitch">
      <a href="?lang=ja"<?php echo $lang === 'ja' ? ' class="on"' : ''; ?>>日本語</a>
      <a href="?lang=en"<?php echo $lang === 'en' ? ' class="on"' : ''; ?>>English</a>
    </div>
    <a class="btn btn-ghost" href="https://kgeo.exbridge.jp/<?php echo $lang === 'en' ? '' : 'kgeo.html'; ?>" target="_blank" rel="noopener"><?php echo htmlspecialchars($T['nav_about'], ENT_QUOTES, 'UTF-8'); ?></a>
    <a class="btn btn-primary" href="?login=1"><?php echo htmlspecialchars($T['nav_login'], ENT_QUOTES, 'UTF-8'); ?></a>
  </nav>
</div></header>

<main class="wrap">
  <section class="hero">
    <div>
      <span class="eyebrow"><span class="dot"></span><?php echo htmlspecialchars($T['eyebrow'], ENT_QUOTES, 'UTF-8'); ?></span>
      <h1><?php echo $T['h1']; ?></h1>
      <p class="lead"><?php echo $T['lead']; ?></p>
      <div class="cta-row">
        <a class="btn btn-primary" href="?login=1"><?php echo htmlspecialchars($T['cta_login'], ENT_QUOTES, 'UTF-8'); ?></a>
        <span class="cta-note"><?php echo htmlspecialchars($T['cta_note'], ENT_QUOTES, 'UTF-8'); ?></span>
      </div>
    </div>
    <div class="hero-card">
      <img src="images/kurage-ecosystem-avatar.png" alt="Kurage">
      <h2><?php echo htmlspecialchars($T['hero_name'], ENT_QUOTES, 'UTF-8'); ?></h2>
      <p><?php echo htmlspecialchars($T['hero_desc'], ENT_QUOTES, 'UTF-8'); ?></p>
    </div>
  </section>

  <section>
    <h2><?php echo htmlspecialchars($T['feat_title'], ENT_QUOTES, 'UTF-8'); ?></h2>
    <p class="sub"><?php echo htmlspecialchars($T['feat_sub'], ENT_QUOTES, 'UTF-8'); ?></p>
    <div class="chips">
      <div class="chip"><?php echo htmlspecialchars($T['chip1'], ENT_QUOTES, 'UTF-8'); ?><span><?php echo htmlspecialchars($T['chip1s'], ENT_QUOTES, 'UTF-8'); ?></span></div>
      <div class="chip"><?php echo htmlspecialchars($T['chip2'], ENT_QUOTES, 'UTF-8'); ?><span><?php echo htmlspecialchars($T['chip2s'], ENT_QUOTES, 'UTF-8'); ?></span></div>
      <div class="chip"><?php echo htmlspecialchars($T['chip3'], ENT_QUOTES, 'UTF-8'); ?><span><?php echo htmlspecialchars($T['chip3s'], ENT_QUOTES, 'UTF-8'); ?></span></div>
      <div class="chip"><?php echo htmlspecialchars($T['chip4'], ENT_QUOTES, 'UTF-8'); ?><span><?php echo htmlspecialchars($T['chip4s'], ENT_QUOTES, 'UTF-8'); ?></span></div>
    </div>
  </section>

  <section>
    <div class="gate">
      <h2><?php echo htmlspecialchars($T['price_title'], ENT_QUOTES, 'UTF-8'); ?></h2>
      <p class="sub" style="margin-bottom:0"><?php echo htmlspecialchars($T['price_sub'], ENT_QUOTES, 'UTF-8'); ?></p>
      <ul>
        <li><?php echo $T['price1']; ?></li>
        <li><?php echo $T['price2']; ?></li>
        <li><?php echo $T['price3']; ?></li>
        <li><?php echo $T['price4']; ?></li>
      </ul>
    </div>
  </section>

  <section>
    <div class="oss-note">
      <h2><?php echo htmlspecialchars($T['oss_title'], ENT_QUOTES, 'UTF-8'); ?></h2>
      <p><?php echo $T['oss_p']; ?></p>
      <small><?php echo htmlspecialchars($T['oss_note'], ENT_QUOTES, 'UTF-8'); ?></small>
    </div>
  </section>

  <section class="faq">
    <h2><?php echo htmlspecialchars($T['faq_title'], ENT_QUOTES, 'UTF-8'); ?></h2>
    <details open><summary><?php echo htmlspecialchars($T['faq1_q'], ENT_QUOTES, 'UTF-8'); ?></summary><p><?php echo htmlspecialchars($T['faq1_a'], ENT_QUOTES, 'UTF-8'); ?></p></details>
    <details><summary><?php echo htmlspecialchars($T['faq2_q'], ENT_QUOTES, 'UTF-8'); ?></summary><p><?php echo htmlspecialchars($T['faq2_a'], ENT_QUOTES, 'UTF-8'); ?></p></details>
    <details><summary><?php echo htmlspecialchars($T['faq3_q'], ENT_QUOTES, 'UTF-8'); ?></summary><p><?php echo htmlspecialchars($T['faq3_a'], ENT_QUOTES, 'UTF-8'); ?></p></details>
  </section>
</main>

<footer class="site"><div class="wrap">
  Kurage GEO — <a href="https://exbridge.jp/"><?php echo htmlspecialchars($T['footer_product'], ENT_QUOTES, 'UTF-8'); ?></a> ·
  <a href="https://github.com/katsushi2441/kgeo" target="_blank" rel="noopener">GitHub</a> ·
  <a href="https://kgeo.exbridge.jp/<?php echo $lang === 'en' ? '' : 'kgeo.html'; ?>" target="_blank" rel="noopener"><?php echo htmlspecialchars($T['nav_about'], ENT_QUOTES, 'UTF-8'); ?></a> ·
  <a href="https://exbridge.jp/contact.php"><?php echo htmlspecialchars($T['footer_contact'], ENT_QUOTES, 'UTF-8'); ?></a>
  <br><br>&copy; <?php echo date('Y'); ?> EXBRIDGE, Inc.
</div></footer>
</body></html><?php
exit;
endif;

$html_path = file_exists(__DIR__ . '/kgeo_app.html')
    ? __DIR__ . '/kgeo_app.html'
    : __DIR__ . '/../static/index.html';
$html = file_get_contents($html_path);
$html = str_replace('href="/static/styles.css"', 'href="?asset=styles.css"', $html);
$html = str_replace('src="/static/app.js" defer', 'src="?asset=app.js" defer', $html);
if ($lang === 'en') { $html = preg_replace('/<html lang="ja">/', '<html lang="en">', $html, 1); }
$bootstrap = '<script>window.KGEO_API_PREFIX="?api=";window.KGEO_CSRF=' . json_encode($csrf) . ';window.KGEO_LANG=' . json_encode($lang) . ';window.KGEO_USER=' . json_encode($session_user) . ';</script>'
    . '<script async src="https://www.googletagmanager.com/gtag/js?id=G-BP0650KDFR"></script>'
    . '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}gtag("js",new Date());gtag("config","G-BP0650KDFR");</script>'
    . '<script>(function(){var s=document.createElement("script");s.src="https://aiknowledgecms.exbridge.jp/simpletrack.php?url="+encodeURIComponent(location.href)+"&ref="+encodeURIComponent(document.referrer);document.head.appendChild(s)})();</script>';
$html = str_replace('</head>', $bootstrap . '</head>', $html);
echo $html;
