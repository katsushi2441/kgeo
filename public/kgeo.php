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
<title>Kurage GEO | AI検索対応を日本語で診断</title><meta name="description" content="AI検索に引用されやすいサイトへ。技術監査とブランド可視性を日本語で確認するKurage GEO。">
<style>body{margin:0;background:#f5fcfd;color:#15334a;font-family:-apple-system,BlinkMacSystemFont,"Noto Sans JP",sans-serif}.wrap{max-width:720px;margin:12vh auto;padding:28px}.card{background:#fff;border:1px solid #dce8ee;border-radius:28px;padding:48px;box-shadow:0 18px 55px rgba(24,75,99,.1);text-align:center}.mark{width:70px;height:70px;margin:auto;display:grid;place-items:center;border-radius:22px;background:#0c9bae;color:#fff;font-size:36px;font-weight:900}h1{font-size:38px;margin:20px 0 10px}p{color:#667b8b;line-height:1.8}.button{display:inline-flex;min-height:50px;align-items:center;margin-top:18px;padding:0 28px;border-radius:14px;background:#0c9bae;color:#fff;text-decoration:none;font-weight:800}</style></head><body><main class="wrap"><section class="card"><div class="mark">G</div><h1>Kurage GEO</h1><p>サイトのAI検索対応を監査し、ブランド言及とURL引用を継続観測します。<br>利用には共通Xアカウントでのログインが必要です。</p><a class="button" href="?login=1">Xでログイン</a></section></main></body></html><?php
exit;
endif;

$html_path = file_exists(__DIR__ . '/kgeo_app.html')
    ? __DIR__ . '/kgeo_app.html'
    : __DIR__ . '/../static/index.html';
$html = file_get_contents($html_path);
$html = str_replace('href="/static/styles.css"', 'href="?asset=styles.css"', $html);
$html = str_replace('src="/static/app.js" defer', 'src="?asset=app.js" defer', $html);
$bootstrap = '<script>window.KGEO_API_PREFIX="?api=";window.KGEO_CSRF=' . json_encode($csrf) . ';</script>';
$html = str_replace('</head>', $bootstrap . '</head>', $html);
echo $html;
