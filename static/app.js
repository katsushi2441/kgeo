const $ = (selector) => document.querySelector(selector);
const state = { sites: [], selected: null, usage: null, billing: null };

// 言語: kgeo.phpがwindow.KGEO_LANGを注入する。ロジックは1本、文言だけ差し替える。
const LANG = window.KGEO_LANG === "en" ? "en" : "ja";
const LOCALE = LANG === "en" ? "en-US" : "ja-JP";
const TT = {
  ja: {
    labels: {
      robots: "AIクローラー",
      llms: "llms.txt",
      schema: "構造化データ",
      meta: "メタ情報",
      content: "コンテンツ",
      signals: "更新シグナル",
      ai_discovery: "AI発見性",
      brand_entity: "ブランド",
      negative_penalty: "減点",
    },
    bandNames: {
      excellent: "非常に良好",
      good: "良好",
      foundation: "改善の土台あり",
      critical: "要改善",
    },
    aeoLabels: {
      answer_first: "結論先出し",
      definitions: "定義文",
      question_answers: "質問と回答",
      evidence: "根拠・出典",
      readability: "読みやすさ",
      intent_coverage: "検索意図",
      claim_risk: "主張リスク",
    },
    engineLabels: {
      citability: "引用適性",
      rag_chunk: "RAG分割",
      context_window: "文脈効率",
      intent_mapping: "検索意図",
      trust_stack: "信頼性",
    },
    usage_loading: "利用状況を取得中",
    diagnosis_admin: "管理者：課金対象外",
    diagnosis_free: "次の診断は初回無料",
    diagnosis_credits: (n) => `診断クレジット ${n}`,
    diagnosis_checking: "診断料金を確認中",
    usage_line: (d, used, limit) => `${d} ・ 今月 AI確認 ${used}/${limit}`,
    empty_sites: "サイトを登録すると、ここに監査履歴が並びます。",
    not_audited: "未診断",
    api_ok: "API 接続中",
    api_error: "API 接続エラー",
    load_failed: (m) => `読み込みに失敗しました: ${m}`,
    last_audit: (d) => `最終監査 ${d}`,
    rec_fallback: "主要な基礎項目は整っています。AI回答での実測へ進んでください。",
    llm_not_ready: "LLMシミュレーションは現在準備中です。GEO・AEO監査は利用できます。",
    no_prompts: "確認する質問はまだありません。",
    checking: "確認中…",
    check_done: (s) => `確認完了：回答可能性 ${s}点`,
    run_failed: (m) => `LLM回答シミュレーションに失敗しました: ${m}`,
    btn_run: "本文を読ませて確認",
    btn_no_llm: "AI接続未設定",
    aeo_notice_next: "再監査するとAEO判定が追加されます。",
    aeo_heading_ja: "日本語で「質問に答えられるか」",
    aeo_heading_en: "英語ページとして「質問に答えられるか」",
    aeo_heading_unknown: "「質問に答えられるか」",
    aeo_pending: "AEOの詳細は次回の監査で計算されます。",
    claim_risk_note: "低いほど安全",
    no_estimates: "推定値がありません。",
    per100: "/ 100",
    history_toggle: (n) => `過去の確認結果 ${n}件を表示`,
    registered_at: (d) => `登録 ${d}`,
    col_supported: "確認できた根拠",
    col_missing: "不足情報",
    col_improve: "改善案",
    answerability: (s) => `回答可能性 ${s}点`,
    legacy_note: "旧形式の回答記録です。外部AI検索の実測ではありません。",
    no_response: "回答なし",
    none: "なし",
    provider_local: "ローカルGemma 4",
    provider_rqdb4ai: "RQDB4AI Gemma 4（0.14）",
    site_registered: "サイトを登録しました。",
    register_failed: (m) => `登録できませんでした: ${m}`,
    auditing: "安全に監査中…",
    audit_start_notice: "ページ・robots.txt・llms.txt・構造化データなどを確認しています。",
    audit_done: "GEO監査が完了しました。",
    audit_need_credit: "2回目以降の診断には、診断クレジットが必要です。",
    audit_failed: (m) => `監査に失敗しました: ${m}`,
    prompt_registered: "監視する質問を登録しました。",
    err_payment: "2回目以降の診断には、200円または20,000 URLAIの診断クレジットが必要です。",
    err_free_audit: "今月の無料監査回数に達しました。",
    err_free_monitor: "今月の無料AI確認回数に達しました。",
    btn_audit_admin: "GEO監査を実行（管理者）",
    btn_audit_free: "初回無料でGEO監査",
    btn_audit_credit: "クレジットでGEO監査",
    btn_audit_paid: "GEO監査を実行（200円 / 20,000 URLAI）",
    billing_checking: "決済情報を確認しています…",
    billing_choose: "支払い方法を選択してください。",
    billing_fetch_failed: (m) => `決済情報を取得できませんでした: ${m}`,
    billing_resume: (m) => `${m} 診断を自動的に再開します。`,
    paypal_desc: "Kurage GEO 診断1回",
    paypal_not_confirmed: "決済を確認できませんでした。",
    paypal_confirm_failed: (m) => `決済確認に失敗しました: ${m}`,
    paypal_error: "PayPal決済でエラーが発生しました。時間をおいて再試行してください。",
    paypal_load_failed: "PayPalの決済画面を読み込めませんでした。",
    wallet_required: "送金元ウォレットアドレスを入力してください。",
    urlai_checking: "Baseチェーン上の送金を確認しています…",
    urlai_not_confirmed: "送金を確認できませんでした。",
    urlai_failed: (m) => `送金確認に失敗しました: ${m}`,
  },
  en: {
    labels: {
      robots: "AI crawlers",
      llms: "llms.txt",
      schema: "Structured data",
      meta: "Meta info",
      content: "Content",
      signals: "Freshness signals",
      ai_discovery: "AI discovery",
      brand_entity: "Brand",
      negative_penalty: "Penalty",
    },
    bandNames: {
      excellent: "Excellent",
      good: "Good",
      foundation: "Solid foundation",
      critical: "Needs work",
    },
    aeoLabels: {
      answer_first: "Answer-first",
      definitions: "Definitions",
      question_answers: "Q&A",
      evidence: "Evidence",
      readability: "Readability",
      intent_coverage: "Search intent",
      claim_risk: "Claim risk",
    },
    engineLabels: {
      citability: "Citability",
      rag_chunk: "RAG chunking",
      context_window: "Context efficiency",
      intent_mapping: "Intent mapping",
      trust_stack: "Trust",
    },
    usage_loading: "Loading usage",
    diagnosis_admin: "Admin: no billing",
    diagnosis_free: "Next audit is free",
    diagnosis_credits: (n) => `Audit credits: ${n}`,
    diagnosis_checking: "Checking pricing",
    usage_line: (d, used, limit) => `${d} ・ AI checks this month ${used}/${limit}`,
    empty_sites: "Register a site and its audit history will appear here.",
    not_audited: "Not audited",
    api_ok: "API connected",
    api_error: "API connection error",
    load_failed: (m) => `Failed to load: ${m}`,
    last_audit: (d) => `Last audit ${d}`,
    rec_fallback: "The key basics are in place. Move on to measuring real AI answers.",
    llm_not_ready: "LLM simulation is being prepared. GEO and AEO audits are available.",
    no_prompts: "No questions to check yet.",
    checking: "Checking…",
    check_done: (s) => `Done. Answerability score: ${s}`,
    run_failed: (m) => `LLM answer simulation failed: ${m}`,
    btn_run: "Check against page content",
    btn_no_llm: "LLM not configured",
    aeo_notice_next: "Re-run the audit to add the AEO evaluation.",
    aeo_heading_ja: "Can it answer questions? (Japanese page)",
    aeo_heading_en: "Can it answer questions? (English page)",
    aeo_heading_unknown: "Can it answer questions?",
    aeo_pending: "AEO details will be computed on the next audit.",
    claim_risk_note: "lower is safer",
    no_estimates: "No estimates available.",
    per100: "/ 100",
    history_toggle: (n) => `Show ${n} previous result(s)`,
    registered_at: (d) => `Registered ${d}`,
    col_supported: "Supported points",
    col_missing: "Missing information",
    col_improve: "Suggestions",
    answerability: (s) => `Answerability ${s}`,
    legacy_note: "Legacy answer record. Not a measurement of external AI search.",
    no_response: "No response",
    none: "None",
    provider_local: "Local Gemma 4",
    provider_rqdb4ai: "RQDB4AI Gemma 4 (0.14)",
    site_registered: "Site registered.",
    register_failed: (m) => `Could not register: ${m}`,
    auditing: "Auditing safely…",
    audit_start_notice: "Checking the page, robots.txt, llms.txt, structured data, and more.",
    audit_done: "GEO audit completed.",
    audit_need_credit: "Audit credits are required from the second audit onward.",
    audit_failed: (m) => `Audit failed: ${m}`,
    prompt_registered: "Monitoring question registered.",
    err_payment: "From the second audit onward, an audit credit (¥200 or 20,000 URLAI) is required.",
    err_free_audit: "You have reached this month's free audit limit.",
    err_free_monitor: "You have reached this month's free AI check limit.",
    btn_audit_admin: "Run GEO audit (admin)",
    btn_audit_free: "Run GEO audit (first one free)",
    btn_audit_credit: "Run GEO audit with credit",
    btn_audit_paid: "Run GEO audit (¥200 / 20,000 URLAI)",
    billing_checking: "Checking payment info…",
    billing_choose: "Choose a payment method.",
    billing_fetch_failed: (m) => `Could not fetch payment info: ${m}`,
    billing_resume: (m) => `${m} The audit will resume automatically.`,
    paypal_desc: "Kurage GEO: 1 audit",
    paypal_not_confirmed: "The payment could not be confirmed.",
    paypal_confirm_failed: (m) => `Payment confirmation failed: ${m}`,
    paypal_error: "The PayPal payment failed. Please try again later.",
    paypal_load_failed: "Could not load the PayPal checkout.",
    wallet_required: "Please enter the sender wallet address.",
    urlai_checking: "Verifying the transfer on Base…",
    urlai_not_confirmed: "The transfer could not be confirmed.",
    urlai_failed: (m) => `Transfer verification failed: ${m}`,
  },
};
const T = TT[LANG];
const labels = T.labels;
const bandNames = T.bandNames;
const aeoLabels = T.aeoLabels;
const engineLabels = T.engineLabels;

// 静的HTMLの文言差し替え（data-i18n / data-i18n-ph）。英語時のみ適用。
const I18N_EN = {
  hero_h1: 'Get your site<br /><span>found</span> by AI search.',
  hero_lead:
    "Audits the technical GEO requirements and Japanese AEO answerability separately, then verifies answerability with an LLM grounded in your page. Not just a score — you get what to fix next, with the evidence.",
  mini_47: "47-item citability audit",
  mini_aeo: "Japanese-specific AEO scoring",
  mini_llm: "Grounded LLM evaluation",
  ws_title: "Your sites",
  price_badge: "First audit free",
  price_text:
    "From the second audit: <b>¥200</b> or <b>20,000 URLAI</b> per audit. No subscription.",
  label_name: "Site name",
  label_url: "Public URL",
  label_brand: "Brand name",
  label_competitors: "Competitor brands (optional, comma-separated)",
  ph_name: "e.g. Kurage GEO",
  ph_brand: "e.g. Kurage",
  ph_competitors: "Competitor A, Competitor B",
  btn_register: "Register site",
  detail_title: "Audit report",
  btn_audit: "Run GEO audit",
  empty_audit:
    'No audit results yet. Run "Run GEO audit" to record your first baseline.',
  band_none: "Not audited",
  h_breakdown: "Score by category",
  h_recommend: "What to fix next",
  h_aeo: 'Can it "answer questions"?',
  h_engine: "AI understanding & citation metrics",
  h_platform: "Per-platform readiness",
  note_platform:
    "Estimates computed from page structure, not actual rankings.",
  h_monitor: "Check answerability against your page",
  monitor_desc:
    "Sends your page content to Gemma 4 or DeepSeek and records answerability, evidence, and missing information. Not real ChatGPT/Gemini search results.",
  ph_prompt: "e.g. Which GEO audit services can I use in Japanese?",
  btn_prompt: "Register question",
  bd_title: "Add audit credits",
  bd_lead:
    "Your first audit is free. After that, <b>1 audit = ¥200 or 20,000 URLAI</b>.",
  bd_credits_label: "Current credits: ",
  bd_paypal_h: "¥200 (PayPal)",
  bd_paypal_note:
    "One audit credit is added when the PayPal payment completes.",
  bd_urlai_h: "20,000 URLAI (Base)",
  bd_urlai_note:
    "Send to the address below, then enter the sender wallet. Bulk transfers add one credit per 20,000 URLAI.",
  ph_wallet: "Sender wallet (0x…)",
  btn_verify: "Verify payment",
  btn_close: "Close",
  btn_logout: "Logout",
};
if (LANG === "en") {
  document.documentElement.lang = "en";
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const value = I18N_EN[el.dataset.i18n];
    if (value) el.innerHTML = value;
  });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => {
    const value = I18N_EN[el.dataset.i18nPh];
    if (value) el.placeholder = value;
  });
  const usage = $("#usage");
  if (usage) usage.textContent = T.usage_loading;
  const status = $("#serviceStatus");
  if (status) status.textContent = "Connecting";
}
document.querySelectorAll(".langswitch a").forEach((a) => {
  if (a.dataset.lang === LANG) a.classList.add("on");
});

// ログインユーザー表示とログアウト（kgeo.phpがwindow.KGEO_USERを注入する）
if (window.KGEO_USER) {
  const chip = $("#userChip");
  const logout = $("#logoutLink");
  if (chip) {
    chip.textContent = `@${window.KGEO_USER}`;
    chip.hidden = false;
  }
  if (logout) logout.hidden = false;
}

async function api(path, options = {}) {
  const target = window.KGEO_API_PREFIX
    ? `${window.KGEO_API_PREFIX}${encodeURIComponent(path)}`
    : path;
  const headers = { "Content-Type": "application/json", ...options.headers };
  if (window.KGEO_CSRF) headers["X-CSRF-Token"] = window.KGEO_CSRF;
  const response = await fetch(target, { headers, ...options });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      detail = (await response.json()).detail || detail;
    } catch (_) {}
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function notice(message = "") {
  const box = $("#notice");
  box.textContent = message;
  box.hidden = !message;
}

function usageText() {
  const u = state.usage;
  if (!u) return T.usage_loading;
  const ml = u.monitor_runs_limit == null ? "∞" : u.monitor_runs_limit;
  const b = state.billing;
  const diagnosis = b
    ? b.admin_bypass
      ? T.diagnosis_admin
      : b.first_free
        ? T.diagnosis_free
        : T.diagnosis_credits(b.credits)
    : T.diagnosis_checking;
  return T.usage_line(diagnosis, u.monitor_runs_used, ml);
}

function renderSites() {
  const root = $("#sites");
  if (!state.sites.length) {
    root.innerHTML = `<div class="empty card">${T.empty_sites}</div>`;
    return;
  }
  root.innerHTML = state.sites
    .map(
      (s) => `<article class="site-card card" data-id="${s.id}" tabindex="0">
    <p class="eyebrow">${escapeHtml(s.brand_name)}</p><h3>${escapeHtml(s.name)}</h3><div class="url">${escapeHtml(s.url)}</div>
    <div class="score-pill">${s.latest_score == null ? `<span>${T.not_audited}</span>` : `<b>${s.latest_score}</b><span>/ 100 ・ ${bandNames[s.latest_band] || s.latest_band}</span>`}</div>
  </article>`,
    )
    .join("");
  root.querySelectorAll(".site-card").forEach((el) => {
    el.onclick = () => selectSite(el.dataset.id);
    el.onkeydown = (e) => {
      if (e.key === "Enter") selectSite(el.dataset.id);
    };
  });
}

async function loadAll() {
  try {
    const billingRequest = window.KGEO_API_PREFIX
      ? api("/billing/status")
      : Promise.resolve({
          audits: 0,
          first_free: true,
          credits: 0,
          price_jpy: 200,
          price_urlai: 20000,
        });
    const [sites, usage, billing] = await Promise.all([
      api("/api/sites"),
      api("/api/usage"),
      billingRequest,
    ]);
    state.sites = sites;
    state.usage = usage;
    state.billing = billing;
    $("#usage").textContent = usageText();
    renderSites();
    $(".status").classList.add("ok");
    $("#serviceStatus").textContent = T.api_ok;
  } catch (e) {
    notice(T.load_failed(e.message));
    $("#serviceStatus").textContent = T.api_error;
  }
}

async function selectSite(id) {
  state.selected = state.sites.find((s) => s.id === id);
  if (!state.selected) return;
  $("#detail").hidden = false;
  $("#detailName").textContent = state.selected.name;
  $("#detailUrl").textContent = state.selected.url;
  $("#detailUrl").href = state.selected.url;
  updateAuditButton();
  $("#detail").scrollIntoView({ behavior: "smooth", block: "start" });
  await Promise.all([loadAudits(), loadPrompts()]);
}

async function loadAudits() {
  const audits = await api(`/api/sites/${state.selected.id}/audits`);
  $("#emptyAudit").hidden = audits.length > 0;
  $("#auditReport").hidden = !audits.length;
  if (!audits.length) return;
  const a = audits[0];
  $("#score").textContent = a.score;
  $(".score-ring").style.setProperty("--score-angle", `${a.score * 3.6}deg`);
  $("#band").textContent = bandNames[a.band] || a.band;
  $("#auditTime").textContent = T.last_audit(
    new Date(a.created_at).toLocaleString(LOCALE),
  );
  $("#breakdown").innerHTML = Object.entries(a.score_breakdown)
    .map(
      ([k, v]) =>
        `<div class="metric"><span>${labels[k] || k}</span><b>${v}</b></div>`,
    )
    .join("");
  $("#recommendations").innerHTML =
    a.recommendations_ja.map((v) => `<li>${escapeHtml(v)}</li>`).join("") ||
    `<li>${T.rec_fallback}</li>`;
  const detail = await api(`/api/audits/${a.id}`);
  renderAdvancedReport(detail.result || {});
}

async function loadPrompts() {
  const items = await api(`/api/sites/${state.selected.id}/prompts`);
  const root = $("#prompts");
  const llmReady = Boolean(state.usage && state.usage.llm_configured);
  const runs = await Promise.all(
    items.map((prompt) => api(`/api/prompts/${prompt.id}/runs`)),
  );
  root.innerHTML =
    (llmReady ? "" : `<p class="notice">${T.llm_not_ready}</p>`) +
    (items.length
      ? items
          .map((prompt, index) => renderPrompt(prompt, runs[index], llmReady))
          .join("")
      : `<p class="muted">${T.no_prompts}</p>`);
  root
    .querySelectorAll("button")
    .forEach((btn) => (btn.onclick = () => runPrompt(btn)));
}

async function runPrompt(button) {
  button.disabled = true;
  button.textContent = T.checking;
  try {
    const r = await api(`/api/prompts/${button.dataset.prompt}/runs`, {
      method: "POST",
    });
    const score = r.analysis?.answerability_score ?? "--";
    notice(T.check_done(score));
    state.usage = await api("/api/usage");
    $("#usage").textContent = usageText();
    await loadPrompts();
  } catch (e) {
    notice(T.run_failed(humanError(e.message)));
  } finally {
    button.disabled = false;
    button.textContent = T.btn_run;
  }
}

function renderAdvancedReport(result) {
  const root = $("#advancedReport");
  const aeo = result.aeo || result.japanese_aeo || {};
  root.hidden = false;
  // 判定に使った言語を見出しに出す（英語ページを日本語基準で見たと誤解させない）
  const heading = $("#aeoHeading");
  if (heading) {
    const analyzed = aeo.analyzed_as || aeo.language;
    heading.textContent =
      analyzed === "en" ? T.aeo_heading_en : analyzed === "ja" ? T.aeo_heading_ja : T.aeo_heading_unknown;
  }
  $("#aeoScore").textContent = aeo.checked ? aeo.score : "--";
  $("#aeoNotice").textContent = aeo.notice || T.aeo_notice_next;
  $("#aeoMetrics").innerHTML =
    Object.entries(aeo.metrics || {})
      .map(([key, value]) =>
        metricBox(
          aeoLabels[key] || key,
          value.score,
          key === "claim_risk" ? T.claim_risk_note : "",
        ),
      )
      .join("") || `<p class="muted">${T.aeo_pending}</p>`;

  const engine = {
    citability: result.citability?.total_score,
    rag_chunk: result.rag_chunk?.chunk_readiness_score,
    context_window: result.context_window?.context_efficiency_score,
    intent_mapping: result.intent_mapping?.score,
    trust_stack:
      result.trust_stack?.composite_score == null
        ? null
        : Math.round((result.trust_stack.composite_score / 25) * 100),
  };
  $("#engineMetrics").innerHTML = Object.entries(engine)
    .map(([key, value]) => metricBox(engineLabels[key], value))
    .join("");

  const platforms = result.platform_citation?.platforms || [];
  const platformLabels = {
    chatgpt: "ChatGPT",
    perplexity: "Perplexity",
    google_ai: "Google AI",
  };
  $("#platformMetrics").innerHTML =
    platforms
      .map((item) =>
        metricBox(platformLabels[item.platform] || item.platform, item.score),
      )
      .join("") || `<p class="muted">${T.no_estimates}</p>`;
}

function metricBox(label, value, note = "") {
  return `<div class="aeo-metric"><span>${escapeHtml(label)}</span><b>${value == null ? "--" : escapeHtml(String(value))}</b><small>${escapeHtml(note || T.per100)}</small></div>`;
}

function renderPrompt(prompt, runs, llmReady) {
  const history = runs || [];
  const latest = history[0];
  const previous = history.slice(1, 6);
  const historyHtml = previous.length
    ? `<details class="history-details"><summary>${T.history_toggle(previous.length)}</summary>${previous.map((run) => renderRun(run)).join("")}</details>`
    : "";
  return `<div class="prompt-item"><div class="prompt-content"><p>${escapeHtml(prompt.prompt)}</p><span class="prompt-meta">${T.registered_at(new Date(prompt.created_at).toLocaleDateString(LOCALE))}</span></div><button class="secondary" data-prompt="${prompt.id}" ${llmReady ? "" : "disabled"}>${llmReady ? T.btn_run : T.btn_no_llm}</button>${latest ? renderRun(latest) : ""}${historyHtml}</div>`;
}

function renderRun(run) {
  const analysis = run.analysis || {};
  const score = analysis.answerability_score ?? "--";
  const columns = [
    [T.col_supported, analysis.supported_points],
    [T.col_missing, analysis.missing_information],
    [T.col_improve, analysis.improvement_suggestions],
  ]
    .map(
      ([title, items]) =>
        `<div class="analysis-box"><b>${title}</b>${listHtml(items)}</div>`,
    )
    .join("");
  return `<div class="run-result"><div class="run-head"><span class="run-badge">${escapeHtml(providerName(run.provider))}</span><span class="run-badge">${escapeHtml(run.model)}</span><span class="run-score">${T.answerability(score)}</span><span class="prompt-meta">${new Date(run.created_at).toLocaleString(LOCALE)}</span></div><p class="scope-note">${escapeHtml(analysis.notice || T.legacy_note)}</p><pre class="ai-response">${escapeHtml(run.response_text || T.no_response)}</pre><div class="analysis-columns">${columns}</div></div>`;
}

function providerName(value) {
  if (value === "ollama-local") return T.provider_local;
  if (value === "ollama-rqdb4ai") return T.provider_rqdb4ai;
  if (value === "deepseek") return "DeepSeek";
  return value || "LLM";
}

function listHtml(items) {
  return Array.isArray(items) && items.length
    ? `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
    : `<span class="prompt-meta">${T.none}</span>`;
}

$("#siteForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target),
    button = e.target.querySelector("button");
  button.disabled = true;
  try {
    const body = {
      name: f.get("name"),
      url: f.get("url"),
      brand_name: f.get("brand_name"),
      competitors: String(f.get("competitors") || "")
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean),
    };
    await api("/api/sites", { method: "POST", body: JSON.stringify(body) });
    e.target.reset();
    notice(T.site_registered);
    await loadAll();
  } catch (err) {
    notice(T.register_failed(humanError(err.message)));
  } finally {
    button.disabled = false;
  }
});

async function runAudit() {
  if (!state.selected) return;
  const b = $("#auditButton");
  b.disabled = true;
  b.textContent = T.auditing;
  notice(T.audit_start_notice);
  try {
    await api(`/api/sites/${state.selected.id}/audits`, { method: "POST" });
    notice(T.audit_done);
    await loadAll();
    state.selected = state.sites.find((s) => s.id === state.selected.id);
    await loadAudits();
  } catch (err) {
    if (err.status === 402 || err.message === "PAYMENT_REQUIRED") {
      notice(T.audit_need_credit);
      await openBilling();
      return;
    }
    notice(T.audit_failed(humanError(err.message)));
  } finally {
    b.disabled = false;
    updateAuditButton();
  }
}

$("#auditButton").addEventListener("click", runAudit);

$("#promptForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!state.selected) return;
  const f = new FormData(e.target),
    button = e.target.querySelector("button");
  button.disabled = true;
  try {
    await api(`/api/sites/${state.selected.id}/prompts`, {
      method: "POST",
      body: JSON.stringify({ prompt: f.get("prompt") }),
    });
    e.target.reset();
    await loadPrompts();
    notice(T.prompt_registered);
  } catch (err) {
    notice(T.register_failed(humanError(err.message)));
  } finally {
    button.disabled = false;
  }
});

function humanError(v) {
  if (v === "PAYMENT_REQUIRED") return T.err_payment;
  if (v === "FREE_AUDIT_LIMIT_REACHED") return T.err_free_audit;
  if (v === "FREE_MONITOR_LIMIT_REACHED") return T.err_free_monitor;
  return v;
}

function updateAuditButton() {
  const button = $("#auditButton");
  if (!button || button.disabled) return;
  if (state.billing?.admin_bypass) {
    button.textContent = T.btn_audit_admin;
  } else if (state.billing?.first_free) {
    button.textContent = T.btn_audit_free;
  } else if ((state.billing?.credits || 0) > 0) {
    button.textContent = T.btn_audit_credit;
  } else {
    button.textContent = T.btn_audit_paid;
  }
}

function billingSay(message, ok = false) {
  const box = $("#billingMsg");
  box.textContent = message;
  box.classList.toggle("ok", ok);
}

async function refreshBilling() {
  if (!window.KGEO_API_PREFIX) return state.billing;
  state.billing = await api("/billing/status");
  $("#usage").textContent = usageText();
  updateAuditButton();
  return state.billing;
}

async function openBilling() {
  const dialog = $("#billingDialog");
  if (!dialog.open) dialog.showModal();
  billingSay(T.billing_checking);
  try {
    const info = await refreshBilling();
    $("#billingCredits").textContent = String(info.credits);
    $("#billingReceiver").textContent = info.urlai_receiver || "-";
    billingSay(T.billing_choose);
    mountPaypal();
  } catch (error) {
    billingSay(T.billing_fetch_failed(humanError(error.message)));
  }
}

async function billingGranted(data) {
  state.billing = { ...(state.billing || {}), credits: data.credits };
  $("#billingCredits").textContent = String(data.credits);
  $("#usage").textContent = usageText();
  billingSay(T.billing_resume(data.message), true);
  window.setTimeout(() => {
    $("#billingDialog").close();
    runAudit();
  }, 1200);
}

function mountPaypal() {
  const info = state.billing;
  const box = $("#kgeoPaypalButtons");
  if (!info?.paypal_client_id || box.dataset.mounted) return;
  const boot = () => {
    if (!window.paypal?.Buttons || box.dataset.mounted) return;
    box.dataset.mounted = "1";
    window.paypal
      .Buttons({
        style: { layout: "horizontal", height: 38, tagline: false },
        createOrder: (_data, actions) =>
          actions.order.create({
            purchase_units: [
              {
                description: T.paypal_desc,
                amount: {
                  currency_code: "JPY",
                  value: String(info.price_jpy),
                },
              },
            ],
          }),
        onApprove: (_data, actions) =>
          actions.order.capture().then(async (order) => {
            try {
              const result = await api("/billing/paypal", {
                method: "POST",
                body: JSON.stringify({ order_id: order.id }),
              });
              if (result.ok) await billingGranted(result);
              else billingSay(result.message || T.paypal_not_confirmed);
            } catch (error) {
              billingSay(T.paypal_confirm_failed(humanError(error.message)));
            }
          }),
        onError: () => billingSay(T.paypal_error),
      })
      .render("#kgeoPaypalButtons");
  };
  if (window.paypal) {
    boot();
    return;
  }
  const script = document.createElement("script");
  script.src = `https://www.paypal.com/sdk/js?client-id=${encodeURIComponent(info.paypal_client_id)}&currency=JPY`;
  script.onload = boot;
  script.onerror = () => billingSay(T.paypal_load_failed);
  document.head.appendChild(script);
}

async function verifyUrlai() {
  const wallet = $("#billingWallet").value.trim();
  if (!wallet) {
    billingSay(T.wallet_required);
    return;
  }
  billingSay(T.urlai_checking);
  const button = $("#billingVerifyUrlai");
  button.disabled = true;
  try {
    const result = await api("/billing/urlai", {
      method: "POST",
      body: JSON.stringify({ wallet }),
    });
    if (result.ok) await billingGranted(result);
    else billingSay(result.message || T.urlai_not_confirmed);
  } catch (error) {
    billingSay(T.urlai_failed(humanError(error.message)));
  } finally {
    button.disabled = false;
  }
}

$("#billingClose").addEventListener("click", () =>
  $("#billingDialog").close(),
);
$("#billingVerifyUrlai").addEventListener("click", verifyUrlai);
function escapeHtml(value) {
  const d = document.createElement("div");
  d.textContent = value;
  return d.innerHTML;
}
loadAll();
