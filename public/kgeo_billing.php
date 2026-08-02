<?php
/**
 * Kurage GEO diagnosis billing.
 *
 * One successful diagnosis per X account is free. Every later successful
 * diagnosis consumes one credit purchased for JPY 200 or 20,000 URLAI.
 */

if (!defined('KGEO_PRICE_JPY')) { define('KGEO_PRICE_JPY', 200); }
if (!defined('KGEO_PRICE_URLAI')) { define('KGEO_PRICE_URLAI', 20000); }
if (!defined('KGEO_BILLING_DATA_DIR')) { define('KGEO_BILLING_DATA_DIR', __DIR__ . '/kgeo_data'); }
if (!defined('KGEO_BILLING_LEDGER')) { define('KGEO_BILLING_LEDGER', KGEO_BILLING_DATA_DIR . '/credits.json'); }
if (!defined('KGEO_PAYPAL_CLIENT_ID')) {
    define('KGEO_PAYPAL_CLIENT_ID', 'AbbwjyEYdGXqSqptChYFw7vxdOzBSZXiNslHASN1bHfxJZnV_borxUJdMzR1gs8njHQxqn69APqn5-MG');
}
if (!defined('KGEO_PAYPAL_SECRET_FILE')) { define('KGEO_PAYPAL_SECRET_FILE', __DIR__ . '/blog/paywall/data/paypal_secret.txt'); }
if (!defined('KGEO_PAYPAL_API')) { define('KGEO_PAYPAL_API', 'https://api-m.paypal.com'); }
if (!defined('KGEO_URLAI_CONTRACT')) { define('KGEO_URLAI_CONTRACT', '0xdaecdda6ad112f0e1e4097fb735dd01d9c33cba3'); }
if (!defined('KGEO_URLAI_RECEIVER')) { define('KGEO_URLAI_RECEIVER', '0x444fadbd6e1fed0cfbf7613b6c9f91b9021eecbd'); }
if (!defined('KGEO_BASE_RPC')) { define('KGEO_BASE_RPC', 'https://mainnet.base.org'); }

function kgeo_bill_default() {
    return array('users' => array(), 'used_orders' => array(), 'used_txs' => array());
}

function kgeo_bill_normalize($data) {
    if (!is_array($data)) { $data = array(); }
    return $data + kgeo_bill_default();
}

function kgeo_bill_load() {
    if (!file_exists(KGEO_BILLING_LEDGER)) { return kgeo_bill_default(); }
    $fp = @fopen(KGEO_BILLING_LEDGER, 'r');
    if (!$fp) { return kgeo_bill_default(); }
    flock($fp, LOCK_SH);
    $raw = stream_get_contents($fp);
    flock($fp, LOCK_UN);
    fclose($fp);
    return kgeo_bill_normalize(json_decode((string)$raw, true));
}

/** Atomically mutate the billing ledger and return a callback-defined result. */
function kgeo_bill_update($callback) {
    if (!is_dir(KGEO_BILLING_DATA_DIR) && !@mkdir(KGEO_BILLING_DATA_DIR, 0705, true)) {
        return array(false, '課金台帳を作成できません');
    }
    $fp = @fopen(KGEO_BILLING_LEDGER, 'c+');
    if (!$fp) { return array(false, '課金台帳を開けません'); }
    if (!flock($fp, LOCK_EX)) { fclose($fp); return array(false, '課金台帳をロックできません'); }
    rewind($fp);
    $data = kgeo_bill_normalize(json_decode((string)stream_get_contents($fp), true));
    $result = $callback($data);
    rewind($fp);
    ftruncate($fp, 0);
    $written = fwrite($fp, json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
    fflush($fp);
    @chmod(KGEO_BILLING_LEDGER, 0600);
    flock($fp, LOCK_UN);
    fclose($fp);
    if ($written === false) { return array(false, '課金台帳を保存できません'); }
    return $result;
}

function kgeo_bill_credits($user) {
    $data = kgeo_bill_load();
    return isset($data['users'][$user]['credits']) ? (int)$data['users'][$user]['credits'] : 0;
}

/** Return free, credit, or need_payment for the next diagnosis. */
function kgeo_bill_gate($user, $successful_audits) {
    if ((int)$successful_audits < 1) { return 'free'; }
    return kgeo_bill_credits($user) >= 1 ? 'credit' : 'need_payment';
}

/** Consume a credit only after the diagnosis API completed successfully. */
function kgeo_bill_commit($user, $mode) {
    if ($mode === 'free') { return true; }
    if ($mode !== 'credit') { return false; }
    $result = kgeo_bill_update(function (&$data) use ($user) {
        $credits = isset($data['users'][$user]['credits']) ? (int)$data['users'][$user]['credits'] : 0;
        if ($credits < 1) { return array(false, '診断クレジットがありません'); }
        $data['users'][$user]['credits'] = $credits - 1;
        $data['users'][$user]['consumed_at'][] = time();
        return array(true, '診断クレジットを1消費しました');
    });
    return !empty($result[0]);
}

function kgeo_bill_grant($user, $credits, $method, $reference) {
    return kgeo_bill_update(function (&$data) use ($user, $credits, $method, $reference) {
        $current = isset($data['users'][$user]['credits']) ? (int)$data['users'][$user]['credits'] : 0;
        $data['users'][$user]['credits'] = $current + (int)$credits;
        $data['users'][$user]['purchases'][] = array(
            'method' => $method,
            'ref' => $reference,
            'n' => (int)$credits,
            'ts' => time(),
        );
        return array(true, '診断クレジットを追加しました');
    });
}

function kgeo_bill_http_json($url, $headers, $post_body = null) {
    $ch = curl_init($url);
    $options = array(
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_CONNECTTIMEOUT => 8,
        CURLOPT_TIMEOUT => 25,
        CURLOPT_HTTPHEADER => $headers,
    );
    if ($post_body !== null) {
        $options[CURLOPT_POST] = true;
        $options[CURLOPT_POSTFIELDS] = $post_body;
    }
    curl_setopt_array($ch, $options);
    $response = curl_exec($ch);
    $status = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    return array($status, json_decode((string)$response, true));
}

function kgeo_bill_grant_paypal($user, $order_id) {
    $order_id = trim((string)$order_id);
    if (!preg_match('/^[A-Z0-9]{8,32}$/i', $order_id)) {
        return array(false, '注文IDの形式が不正です');
    }
    $existing = kgeo_bill_load();
    if (in_array($order_id, $existing['used_orders'], true)) {
        return array(false, 'この注文IDは既に使用されています');
    }
    $secret = file_exists(KGEO_PAYPAL_SECRET_FILE) ? trim((string)@file_get_contents(KGEO_PAYPAL_SECRET_FILE)) : '';
    if ($secret === '') { return array(false, '決済設定が未完了です。運営にご連絡ください'); }
    list($status, $token) = kgeo_bill_http_json(
        KGEO_PAYPAL_API . '/v1/oauth2/token',
        array(
            'Authorization: Basic ' . base64_encode(KGEO_PAYPAL_CLIENT_ID . ':' . $secret),
            'Content-Type: application/x-www-form-urlencoded',
        ),
        'grant_type=client_credentials'
    );
    if ($status !== 200 || empty($token['access_token'])) {
        return array(false, 'PayPal認証に失敗しました');
    }
    list($status, $order) = kgeo_bill_http_json(
        KGEO_PAYPAL_API . '/v2/checkout/orders/' . rawurlencode($order_id),
        array('Authorization: Bearer ' . $token['access_token'], 'Content-Type: application/json')
    );
    if ($status !== 200 || !is_array($order)) { return array(false, '注文が見つかりません'); }
    if (($order['status'] ?? '') !== 'COMPLETED') {
        return array(false, '決済が完了していません(status=' . ($order['status'] ?? '?') . ')');
    }
    $purchase = $order['purchase_units'][0] ?? array();
    $amount = $purchase['amount'] ?? ($purchase['payments']['captures'][0]['amount'] ?? array());
    if (($amount['currency_code'] ?? '') !== 'JPY' || (float)($amount['value'] ?? 0) < KGEO_PRICE_JPY) {
        return array(false, '決済金額が一致しません');
    }
    return kgeo_bill_update(function (&$data) use ($user, $order_id) {
        if (in_array($order_id, $data['used_orders'], true)) {
            return array(false, 'この注文IDは既に使用されています');
        }
        $data['used_orders'][] = $order_id;
        $current = isset($data['users'][$user]['credits']) ? (int)$data['users'][$user]['credits'] : 0;
        $data['users'][$user]['credits'] = $current + 1;
        $data['users'][$user]['purchases'][] = array(
            'method' => 'paypal', 'ref' => $order_id, 'n' => 1, 'ts' => time(),
        );
        return array(true, '200円の決済を確認し、診断クレジットを1追加しました');
    });
}

function kgeo_bill_rpc($method, $params) {
    $body = json_encode(array('jsonrpc' => '2.0', 'id' => 1, 'method' => $method, 'params' => $params));
    $ch = curl_init(KGEO_BASE_RPC);
    curl_setopt_array($ch, array(
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => $body,
        CURLOPT_HTTPHEADER => array('Content-Type: application/json'),
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_CONNECTTIMEOUT => 8,
        CURLOPT_TIMEOUT => 20,
    ));
    $response = curl_exec($ch);
    curl_close($ch);
    $decoded = json_decode((string)$response, true);
    return isset($decoded['result']) ? $decoded['result'] : null;
}

function kgeo_bill_topic_address($address) {
    return '0x' . str_pad(substr(strtolower($address), 2), 64, '0', STR_PAD_LEFT);
}

function kgeo_bill_hex_to_tokens($hex) {
    $hex = ltrim(str_replace('0x', '', (string)$hex), '0');
    if ($hex === '') { return 0.0; }
    if (function_exists('bcadd')) {
        $decimal = '0';
        foreach (str_split($hex) as $character) {
            $decimal = bcadd(bcmul($decimal, '16'), (string)hexdec($character));
        }
        return (float)bcdiv($decimal, bcpow('10', '18'), 6);
    }
    $value = 0.0;
    foreach (str_split($hex) as $character) { $value = $value * 16 + hexdec($character); }
    return $value / 1e18;
}

function kgeo_bill_grant_urlai($user, $wallet) {
    $wallet = strtolower(trim((string)$wallet));
    if (!preg_match('/^0x[a-f0-9]{40}$/', $wallet)) {
        return array(false, 'ウォレットアドレスの形式が不正です');
    }
    $latest_hex = kgeo_bill_rpc('eth_blockNumber', array());
    if (!$latest_hex) { return array(false, 'Baseチェーンに接続できませんでした。少し待って再試行してください'); }
    $latest = hexdec($latest_hex);
    $topic0 = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef';
    $found = array();
    for ($index = 0; $index < 8; $index++) {
        $to = $latest - $index * 50000;
        $from = max(0, $to - 49999);
        $logs = kgeo_bill_rpc('eth_getLogs', array(array(
            'address' => KGEO_URLAI_CONTRACT,
            'topics' => array($topic0, kgeo_bill_topic_address($wallet), kgeo_bill_topic_address(KGEO_URLAI_RECEIVER)),
            'fromBlock' => '0x' . dechex($from),
            'toBlock' => '0x' . dechex($to),
        )));
        if (!is_array($logs)) { continue; }
        foreach ($logs as $log) {
            $key = strtolower(($log['transactionHash'] ?? '') . ':' . ($log['logIndex'] ?? ''));
            if ($key !== ':') { $found[$key] = kgeo_bill_hex_to_tokens($log['data'] ?? '0x0'); }
        }
    }
    return kgeo_bill_update(function (&$data) use ($user, $wallet, $found) {
        $unused = array();
        foreach ($found as $key => $amount) {
            if (!in_array($key, $data['used_txs'], true)) { $unused[$key] = $amount; }
        }
        $total = array_sum($unused);
        $credits = (int)floor($total / KGEO_PRICE_URLAI);
        if ($credits < 1) {
            return array(false, sprintf(
                '未使用の受領を確認できませんでした（確認額: %s URLAI）。%s URLAIを送金後、数十秒待って再試行してください',
                number_format($total),
                number_format(KGEO_PRICE_URLAI)
            ));
        }
        foreach (array_keys($unused) as $key) { $data['used_txs'][] = $key; }
        $current = isset($data['users'][$user]['credits']) ? (int)$data['users'][$user]['credits'] : 0;
        $data['users'][$user]['credits'] = $current + $credits;
        $data['users'][$user]['purchases'][] = array(
            'method' => 'urlai',
            'ref' => $wallet . ':' . implode(',', array_keys($unused)),
            'n' => $credits,
            'ts' => time(),
        );
        return array(true, sprintf(
            '%s URLAIの受領を確認し、診断クレジットを%d追加しました',
            number_format($total),
            $credits
        ));
    });
}
