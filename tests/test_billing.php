<?php
declare(strict_types=1);

$temp = sys_get_temp_dir() . '/kgeo-billing-' . bin2hex(random_bytes(6));
define('KGEO_BILLING_DATA_DIR', $temp);
define('KGEO_BILLING_LEDGER', $temp . '/credits.json');
require dirname(__DIR__) . '/public/kgeo_billing.php';

function assert_same($expected, $actual, string $message): void {
    if ($expected !== $actual) {
        fwrite(STDERR, sprintf(
            "FAIL: %s\nexpected: %s\nactual: %s\n",
            $message,
            var_export($expected, true),
            var_export($actual, true)
        ));
        exit(1);
    }
}

$user = 'billing-test-user';
assert_same('free', kgeo_bill_gate($user, 0), '最初の成功前は無料');
assert_same('need_payment', kgeo_bill_gate($user, 1), '過去の診断があれば支払いが必要');
assert_same(true, kgeo_bill_commit($user, 'free'), '無料診断はクレジットを消費しない');
assert_same(0, kgeo_bill_credits($user), '無料診断後もクレジットは0');

[$ok] = kgeo_bill_grant($user, 2, 'test', 'test-purchase');
assert_same(true, $ok, 'テスト用クレジットを付与できる');
assert_same(2, kgeo_bill_credits($user), 'クレジットが2件になる');
assert_same('credit', kgeo_bill_gate($user, 1), '残高があれば診断できる');
assert_same(true, kgeo_bill_commit($user, 'credit'), '成功時にクレジットを消費できる');
assert_same(1, kgeo_bill_credits($user), '1クレジットだけ消費する');
assert_same(false, kgeo_bill_commit($user, 'unknown'), '不明なモードでは消費しない');
assert_same(1, kgeo_bill_credits($user), '不明なモードの残高は変わらない');

[$wallet_ok] = kgeo_bill_grant_urlai($user, 'not-a-wallet');
assert_same(false, $wallet_ok, '不正なウォレットはRPC通信前に拒否する');

assert_same(true, is_file(KGEO_BILLING_LEDGER), '課金台帳が作成される');
$saved = json_decode((string) file_get_contents(KGEO_BILLING_LEDGER), true);
assert_same(1, $saved['users'][$user]['credits'], '保存済み残高が一致する');
assert_same('test-purchase', $saved['users'][$user]['purchases'][0]['ref'], '購入参照を記録する');

echo "billing tests passed\n";
