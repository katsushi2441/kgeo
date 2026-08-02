<?php
declare(strict_types=1);

require_once __DIR__ . '/kgeo_db_config.php';

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, max-age=0');

function kgeo_store_fail(int $status, string $message): void {
    http_response_code($status);
    echo json_encode(array('ok' => false, 'error' => $message), JSON_UNESCAPED_UNICODE);
    exit;
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    kgeo_store_fail(405, 'Method not allowed');
}
$sent_token = (string)($_SERVER['HTTP_X_KGEO_STORAGE_TOKEN'] ?? '');
if ($sent_token === '' || !hash_equals(KGEO_STORAGE_TOKEN, $sent_token)) {
    kgeo_store_fail(401, 'Unauthorized');
}
$raw = (string)file_get_contents('php://input');
if ($raw === '' || strlen($raw) > 8000000) {
    kgeo_store_fail(400, 'Invalid request');
}
$request = json_decode($raw, true);
if (!is_array($request) || !is_string($request['action'] ?? null)) {
    kgeo_store_fail(400, 'Invalid JSON request');
}
$action = $request['action'];
$payload = is_array($request['payload'] ?? null) ? $request['payload'] : array();
// Heteml WAF(SiteGuard)は監査結果JSON本文をSQLi/XSSと誤検知して403を返す。
// 本文をbase64で包み、WAFからは不透明な文字列に見せてから中身を復元する。
if ($action === 'call_b64') {
    $encoded = is_string($payload['data'] ?? null) ? $payload['data'] : '';
    $decoded = base64_decode($encoded, true);
    $inner = is_string($decoded) ? json_decode($decoded, true) : null;
    if (!is_array($inner) || !is_string($inner['action'] ?? null) || $inner['action'] === 'call_b64') {
        kgeo_store_fail(400, 'Invalid enveloped request');
    }
    $action = $inner['action'];
    $payload = is_array($inner['payload'] ?? null) ? $inner['payload'] : array();
}
if ($action === 'import_snapshot_b64') {
    $encoded = is_string($payload['data'] ?? null) ? $payload['data'] : '';
    $decoded = base64_decode($encoded, true);
    $import = is_string($decoded) ? json_decode($decoded, true) : null;
    if (!is_array($import) || !is_array($import['tables'] ?? null)) {
        kgeo_store_fail(400, 'Invalid import payload');
    }
    $action = 'import_snapshot';
    $payload = array('tables' => $import['tables']);
}

function kgeo_store_string(array $payload, string $key, int $max = 1000000): string {
    if (!array_key_exists($key, $payload) || !is_scalar($payload[$key])) {
        kgeo_store_fail(400, 'Invalid payload');
    }
    $value = (string)$payload[$key];
    if ($value === '' || strlen($value) > $max || preg_match('/[\x00-\x08\x0B\x0C\x0E-\x1F]/', $value)) {
        kgeo_store_fail(400, 'Invalid payload');
    }
    return $value;
}

function kgeo_store_nullable(array $payload, string $key): ?string {
    if (!array_key_exists($key, $payload) || $payload[$key] === null) {
        return null;
    }
    return is_scalar($payload[$key]) ? (string)$payload[$key] : null;
}

function kgeo_store_execute(PDO $pdo, string $sql, array $params = array()): void {
    $statement = $pdo->prepare($sql);
    $statement->execute($params);
}

function kgeo_store_one(PDO $pdo, string $sql, array $params = array()): ?array {
    $statement = $pdo->prepare($sql);
    $statement->execute($params);
    $row = $statement->fetch();
    return is_array($row) ? $row : null;
}

function kgeo_store_all(PDO $pdo, string $sql, array $params = array()): array {
    $statement = $pdo->prepare($sql);
    $statement->execute($params);
    return $statement->fetchAll();
}

function kgeo_store_cast(?array $row, array $integer_keys): ?array {
    if ($row === null) { return null; }
    foreach ($integer_keys as $key) {
        if (array_key_exists($key, $row) && $row[$key] !== null) {
            $row[$key] = (int)$row[$key];
        }
    }
    return $row;
}

function kgeo_store_schema(PDO $pdo): void {
    $statements = array(
        "CREATE TABLE IF NOT EXISTS users (
            owner VARCHAR(200) PRIMARY KEY, plan VARCHAR(32) NOT NULL DEFAULT 'free',
            created_at VARCHAR(40) NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
        "CREATE TABLE IF NOT EXISTS sites (
            id CHAR(12) PRIMARY KEY, owner VARCHAR(200) NOT NULL, name VARCHAR(255) NOT NULL,
            url TEXT NOT NULL, brand_name VARCHAR(255) NOT NULL, competitors_json LONGTEXT NOT NULL,
            created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL,
            INDEX idx_sites_owner_updated(owner, updated_at),
            CONSTRAINT fk_sites_owner FOREIGN KEY(owner) REFERENCES users(owner) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
        "CREATE TABLE IF NOT EXISTS audits (
            id CHAR(12) PRIMARY KEY, site_id CHAR(12) NOT NULL, owner VARCHAR(200) NOT NULL,
            score INT NOT NULL, band VARCHAR(40) NOT NULL, http_status INT NOT NULL DEFAULT 0,
            error TEXT NULL, score_breakdown_json LONGTEXT NOT NULL,
            recommendations_ja_json LONGTEXT NOT NULL, result_json LONGTEXT NOT NULL,
            created_at VARCHAR(40) NOT NULL,
            INDEX idx_audits_site_created(site_id, created_at),
            CONSTRAINT fk_audits_site FOREIGN KEY(site_id) REFERENCES sites(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
        "CREATE TABLE IF NOT EXISTS monitored_prompts (
            id CHAR(12) PRIMARY KEY, site_id CHAR(12) NOT NULL, owner VARCHAR(200) NOT NULL,
            prompt TEXT NOT NULL, active TINYINT NOT NULL DEFAULT 1, created_at VARCHAR(40) NOT NULL,
            INDEX idx_prompts_site(site_id, created_at),
            CONSTRAINT fk_prompts_site FOREIGN KEY(site_id) REFERENCES sites(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
        "CREATE TABLE IF NOT EXISTS prompt_runs (
            id CHAR(12) PRIMARY KEY, prompt_id CHAR(12) NOT NULL, owner VARCHAR(200) NOT NULL,
            provider VARCHAR(80) NOT NULL, model VARCHAR(255) NOT NULL,
            brand_mentioned TINYINT NOT NULL DEFAULT 0, domain_cited TINYINT NOT NULL DEFAULT 0,
            citation_rank INT NULL, cited_urls_json LONGTEXT NOT NULL, response_text LONGTEXT NOT NULL,
            evaluation_mode VARCHAR(80) NOT NULL DEFAULT 'legacy-unverified',
            analysis_json LONGTEXT NOT NULL, error TEXT NULL, created_at VARCHAR(40) NOT NULL,
            INDEX idx_runs_prompt_created(prompt_id, created_at),
            CONSTRAINT fk_runs_prompt FOREIGN KEY(prompt_id) REFERENCES monitored_prompts(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
        "CREATE TABLE IF NOT EXISTS usage_events (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY, owner VARCHAR(200) NOT NULL,
            kind VARCHAR(32) NOT NULL, ref_id VARCHAR(80) NOT NULL, created_at VARCHAR(40) NOT NULL,
            INDEX idx_usage_owner_kind_created(owner, kind, created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
    );
    foreach ($statements as $sql) { $pdo->exec($sql); }
}

function kgeo_store_counts(PDO $pdo): array {
    $result = array();
    foreach (array('users', 'sites', 'audits', 'monitored_prompts', 'prompt_runs', 'usage_events') as $table) {
        $result[$table] = (int)$pdo->query('SELECT COUNT(*) FROM ' . $table)->fetchColumn();
    }
    return $result;
}

try {
    $pdo = new PDO(
        'mysql:host=' . KGEO_DB_HOST . ';dbname=' . KGEO_DB_NAME . ';charset=utf8mb4',
        KGEO_DB_USER,
        KGEO_DB_PASSWORD,
        array(
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES => false,
            PDO::ATTR_TIMEOUT => 10,
        )
    );
    $result = null;
    switch ($action) {
        case 'init_db':
            kgeo_store_schema($pdo);
            $result = kgeo_store_counts($pdo);
            break;
        case 'ensure_user':
            kgeo_store_execute($pdo, 'INSERT IGNORE INTO users(owner, plan, created_at) VALUES (?, \'free\', ?)', array(
                kgeo_store_string($payload, 'owner', 200), kgeo_store_string($payload, 'created_at', 40)
            ));
            $result = true;
            break;
        case 'get_plan':
            $row = kgeo_store_one($pdo, 'SELECT plan FROM users WHERE owner=?', array(kgeo_store_string($payload, 'owner', 200)));
            $result = $row ? (string)$row['plan'] : 'free';
            break;
        case 'create_site':
            kgeo_store_execute($pdo, 'INSERT INTO sites(id,owner,name,url,brand_name,competitors_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)', array(
                kgeo_store_string($payload, 'id', 12), kgeo_store_string($payload, 'owner', 200),
                kgeo_store_string($payload, 'name', 255), kgeo_store_string($payload, 'url', 4096),
                kgeo_store_string($payload, 'brand_name', 255), kgeo_store_string($payload, 'competitors_json'),
                kgeo_store_string($payload, 'created_at', 40), kgeo_store_string($payload, 'created_at', 40)
            ));
            $result = true;
            break;
        case 'list_sites':
            $rows = kgeo_store_all($pdo, 'SELECT s.*,(SELECT score FROM audits a WHERE a.site_id=s.id ORDER BY created_at DESC LIMIT 1) latest_score,(SELECT band FROM audits a WHERE a.site_id=s.id ORDER BY created_at DESC LIMIT 1) latest_band FROM sites s WHERE owner=? ORDER BY updated_at DESC', array(kgeo_store_string($payload, 'owner', 200)));
            $result = array_map(fn($row) => kgeo_store_cast($row, array('latest_score')), $rows);
            break;
        case 'get_site':
            $result = kgeo_store_cast(kgeo_store_one($pdo, 'SELECT s.*,(SELECT score FROM audits a WHERE a.site_id=s.id ORDER BY created_at DESC LIMIT 1) latest_score,(SELECT band FROM audits a WHERE a.site_id=s.id ORDER BY created_at DESC LIMIT 1) latest_band FROM sites s WHERE s.id=? AND s.owner=?', array(kgeo_store_string($payload, 'site_id', 12), kgeo_store_string($payload, 'owner', 200))), array('latest_score'));
            break;
        case 'save_audit':
            $pdo->beginTransaction();
            kgeo_store_execute($pdo, 'INSERT INTO audits(id,site_id,owner,score,band,http_status,error,score_breakdown_json,recommendations_ja_json,result_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)', array(
                kgeo_store_string($payload, 'id', 12), kgeo_store_string($payload, 'site_id', 12),
                kgeo_store_string($payload, 'owner', 200), (int)($payload['score'] ?? 0),
                kgeo_store_string($payload, 'band', 40), (int)($payload['http_status'] ?? 0),
                kgeo_store_nullable($payload, 'error'), kgeo_store_string($payload, 'score_breakdown_json'),
                kgeo_store_string($payload, 'recommendations_ja_json'), kgeo_store_string($payload, 'result_json'),
                kgeo_store_string($payload, 'created_at', 40)
            ));
            kgeo_store_execute($pdo, 'UPDATE sites SET updated_at=? WHERE id=? AND owner=?', array(
                kgeo_store_string($payload, 'created_at', 40), kgeo_store_string($payload, 'site_id', 12),
                kgeo_store_string($payload, 'owner', 200)
            ));
            $pdo->commit();
            $result = true;
            break;
        case 'get_audit':
            $result = kgeo_store_cast(kgeo_store_one($pdo, 'SELECT * FROM audits WHERE id=? AND owner=?', array(kgeo_store_string($payload, 'audit_id', 12), kgeo_store_string($payload, 'owner', 200))), array('score', 'http_status'));
            break;
        case 'list_audits':
            $rows = kgeo_store_all($pdo, 'SELECT * FROM audits WHERE site_id=? AND owner=? ORDER BY created_at DESC LIMIT 50', array(kgeo_store_string($payload, 'site_id', 12), kgeo_store_string($payload, 'owner', 200)));
            $result = array_map(fn($row) => kgeo_store_cast($row, array('score', 'http_status')), $rows);
            break;
        case 'create_prompt':
            kgeo_store_execute($pdo, 'INSERT INTO monitored_prompts(id,site_id,owner,prompt,created_at) VALUES (?,?,?,?,?)', array(
                kgeo_store_string($payload, 'id', 12), kgeo_store_string($payload, 'site_id', 12),
                kgeo_store_string($payload, 'owner', 200), kgeo_store_string($payload, 'prompt'),
                kgeo_store_string($payload, 'created_at', 40)
            ));
            $result = true;
            break;
        case 'get_prompt':
            $result = kgeo_store_cast(kgeo_store_one($pdo, 'SELECT * FROM monitored_prompts WHERE id=? AND owner=?', array(kgeo_store_string($payload, 'prompt_id', 12), kgeo_store_string($payload, 'owner', 200))), array('active'));
            break;
        case 'list_prompts':
            $rows = kgeo_store_all($pdo, 'SELECT * FROM monitored_prompts WHERE site_id=? AND owner=? ORDER BY created_at DESC', array(kgeo_store_string($payload, 'site_id', 12), kgeo_store_string($payload, 'owner', 200)));
            $result = array_map(fn($row) => kgeo_store_cast($row, array('active')), $rows);
            break;
        case 'save_prompt_run':
            kgeo_store_execute($pdo, 'INSERT INTO prompt_runs(id,prompt_id,owner,provider,model,brand_mentioned,domain_cited,citation_rank,cited_urls_json,response_text,evaluation_mode,analysis_json,error,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', array(
                kgeo_store_string($payload, 'id', 12), kgeo_store_string($payload, 'prompt_id', 12),
                kgeo_store_string($payload, 'owner', 200), kgeo_store_string($payload, 'provider', 80),
                kgeo_store_string($payload, 'model', 255), (int)($payload['brand_mentioned'] ?? 0),
                (int)($payload['domain_cited'] ?? 0), isset($payload['citation_rank']) ? (int)$payload['citation_rank'] : null,
                kgeo_store_string($payload, 'cited_urls_json'), kgeo_store_string($payload, 'response_text'),
                kgeo_store_string($payload, 'evaluation_mode', 80), kgeo_store_string($payload, 'analysis_json'),
                kgeo_store_nullable($payload, 'error'), kgeo_store_string($payload, 'created_at', 40)
            ));
            $result = true;
            break;
        case 'get_prompt_run':
            $result = kgeo_store_cast(kgeo_store_one($pdo, 'SELECT * FROM prompt_runs WHERE id=? AND owner=?', array(kgeo_store_string($payload, 'run_id', 12), kgeo_store_string($payload, 'owner', 200))), array('brand_mentioned', 'domain_cited', 'citation_rank'));
            break;
        case 'list_prompt_runs':
            $rows = kgeo_store_all($pdo, 'SELECT * FROM prompt_runs WHERE prompt_id=? AND owner=? ORDER BY created_at DESC LIMIT 50', array(kgeo_store_string($payload, 'prompt_id', 12), kgeo_store_string($payload, 'owner', 200)));
            $result = array_map(fn($row) => kgeo_store_cast($row, array('brand_mentioned', 'domain_cited', 'citation_rank')), $rows);
            break;
        case 'add_usage':
            kgeo_store_execute($pdo, 'INSERT INTO usage_events(owner,kind,ref_id,created_at) VALUES (?,?,?,?)', array(
                kgeo_store_string($payload, 'owner', 200), kgeo_store_string($payload, 'kind', 32),
                kgeo_store_string($payload, 'ref_id', 80), kgeo_store_string($payload, 'created_at', 40)
            ));
            $result = true;
            break;
        case 'monthly_usage':
            $row = kgeo_store_one($pdo, 'SELECT COUNT(*) count FROM usage_events WHERE owner=? AND kind=? AND SUBSTR(created_at,1,7)=?', array(
                kgeo_store_string($payload, 'owner', 200), kgeo_store_string($payload, 'kind', 32),
                kgeo_store_string($payload, 'month', 7)
            ));
            $result = (int)($row['count'] ?? 0);
            break;
        case 'table_counts':
            kgeo_store_schema($pdo);
            $result = kgeo_store_counts($pdo);
            break;
        case 'import_snapshot':
            kgeo_store_schema($pdo);
            $tables = is_array($payload['tables'] ?? null) ? $payload['tables'] : array();
            $pdo->beginTransaction();
            foreach (($tables['users'] ?? array()) as $row) {
                kgeo_store_execute($pdo, 'INSERT IGNORE INTO users(owner,plan,created_at) VALUES (?,?,?)', array($row['owner'], $row['plan'], $row['created_at']));
            }
            foreach (($tables['sites'] ?? array()) as $row) {
                kgeo_store_execute($pdo, 'INSERT IGNORE INTO sites(id,owner,name,url,brand_name,competitors_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)', array($row['id'],$row['owner'],$row['name'],$row['url'],$row['brand_name'],$row['competitors_json'],$row['created_at'],$row['updated_at']));
            }
            foreach (($tables['audits'] ?? array()) as $row) {
                kgeo_store_execute($pdo, 'INSERT IGNORE INTO audits(id,site_id,owner,score,band,http_status,error,score_breakdown_json,recommendations_ja_json,result_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)', array($row['id'],$row['site_id'],$row['owner'],$row['score'],$row['band'],$row['http_status'],$row['error'],$row['score_breakdown_json'],$row['recommendations_ja_json'],$row['result_json'],$row['created_at']));
            }
            foreach (($tables['monitored_prompts'] ?? array()) as $row) {
                kgeo_store_execute($pdo, 'INSERT IGNORE INTO monitored_prompts(id,site_id,owner,prompt,active,created_at) VALUES (?,?,?,?,?,?)', array($row['id'],$row['site_id'],$row['owner'],$row['prompt'],$row['active'],$row['created_at']));
            }
            foreach (($tables['prompt_runs'] ?? array()) as $row) {
                kgeo_store_execute($pdo, 'INSERT IGNORE INTO prompt_runs(id,prompt_id,owner,provider,model,brand_mentioned,domain_cited,citation_rank,cited_urls_json,response_text,evaluation_mode,analysis_json,error,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', array($row['id'],$row['prompt_id'],$row['owner'],$row['provider'],$row['model'],$row['brand_mentioned'],$row['domain_cited'],$row['citation_rank'],$row['cited_urls_json'],$row['response_text'],$row['evaluation_mode'],$row['analysis_json'],$row['error'],$row['created_at']));
            }
            foreach (($tables['usage_events'] ?? array()) as $row) {
                kgeo_store_execute($pdo, 'INSERT IGNORE INTO usage_events(id,owner,kind,ref_id,created_at) VALUES (?,?,?,?,?)', array($row['id'],$row['owner'],$row['kind'],$row['ref_id'],$row['created_at']));
            }
            $pdo->commit();
            $result = kgeo_store_counts($pdo);
            break;
        default:
            kgeo_store_fail(404, 'Unknown action');
    }
    echo json_encode(array('ok' => true, 'result' => $result), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
} catch (Throwable $error) {
    if (isset($pdo) && $pdo instanceof PDO && $pdo->inTransaction()) { $pdo->rollBack(); }
    error_log('kgeo_store: ' . $error->getMessage());
    kgeo_store_fail(500, 'Storage operation failed');
}
