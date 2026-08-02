const $ = (selector) => document.querySelector(selector);
const state = { sites: [], selected: null, usage: null, billing: null };
const labels = {
  robots: "AIクローラー",
  llms: "llms.txt",
  schema: "構造化データ",
  meta: "メタ情報",
  content: "コンテンツ",
  signals: "更新シグナル",
  ai_discovery: "AI発見性",
  brand_entity: "ブランド",
  negative_penalty: "減点",
};
const bandNames = {
  excellent: "非常に良好",
  good: "良好",
  foundation: "改善の土台あり",
  critical: "要改善",
};
const aeoLabels = {
  answer_first: "結論先出し",
  definitions: "定義文",
  question_answers: "質問と回答",
  evidence: "根拠・出典",
  readability: "日本語の読みやすさ",
  intent_coverage: "検索意図",
  claim_risk: "主張リスク",
};
const engineLabels = {
  citability: "引用適性",
  rag_chunk: "RAG分割",
  context_window: "文脈効率",
  intent_mapping: "検索意図",
  trust_stack: "信頼性",
};

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
  if (!u) return "利用状況を取得中";
  const ml = u.monitor_runs_limit == null ? "∞" : u.monitor_runs_limit;
  const b = state.billing;
  const diagnosis = b
    ? b.first_free
      ? "次の診断は初回無料"
      : `診断クレジット ${b.credits}`
    : "診断料金を確認中";
  return `${diagnosis} ・ 今月 AI確認 ${u.monitor_runs_used}/${ml}`;
}

function renderSites() {
  const root = $("#sites");
  if (!state.sites.length) {
    root.innerHTML =
      '<div class="empty card">サイトを登録すると、ここに監査履歴が並びます。</div>';
    return;
  }
  root.innerHTML = state.sites
    .map(
      (s) => `<article class="site-card card" data-id="${s.id}" tabindex="0">
    <p class="eyebrow">${escapeHtml(s.brand_name)}</p><h3>${escapeHtml(s.name)}</h3><div class="url">${escapeHtml(s.url)}</div>
    <div class="score-pill">${s.latest_score == null ? "<span>未診断</span>" : `<b>${s.latest_score}</b><span>/ 100 ・ ${bandNames[s.latest_band] || s.latest_band}</span>`}</div>
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
    $("#serviceStatus").textContent = "API 接続中";
  } catch (e) {
    notice(`読み込みに失敗しました: ${e.message}`);
    $("#serviceStatus").textContent = "API 接続エラー";
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
  $("#auditTime").textContent =
    `最終監査 ${new Date(a.created_at).toLocaleString("ja-JP")}`;
  $("#breakdown").innerHTML = Object.entries(a.score_breakdown)
    .map(
      ([k, v]) =>
        `<div class="metric"><span>${labels[k] || k}</span><b>${v}</b></div>`,
    )
    .join("");
  $("#recommendations").innerHTML =
    a.recommendations_ja.map((v) => `<li>${escapeHtml(v)}</li>`).join("") ||
    "<li>主要な基礎項目は整っています。AI回答での実測へ進んでください。</li>";
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
    (llmReady
      ? ""
      : '<p class="notice">LLMシミュレーションは現在準備中です。GEO・AEO監査は利用できます。</p>') +
    (items.length
      ? items
          .map((prompt, index) => renderPrompt(prompt, runs[index], llmReady))
          .join("")
      : '<p class="muted">確認する質問はまだありません。</p>');
  root
    .querySelectorAll("button")
    .forEach((btn) => (btn.onclick = () => runPrompt(btn)));
}

async function runPrompt(button) {
  button.disabled = true;
  button.textContent = "確認中…";
  try {
    const r = await api(`/api/prompts/${button.dataset.prompt}/runs`, {
      method: "POST",
    });
    const score = r.analysis?.answerability_score ?? "--";
    notice(`確認完了：回答可能性 ${score}点`);
    state.usage = await api("/api/usage");
    $("#usage").textContent = usageText();
    await loadPrompts();
  } catch (e) {
    notice(`LLM回答シミュレーションに失敗しました: ${humanError(e.message)}`);
  } finally {
    button.disabled = false;
    button.textContent = "本文を読ませて確認";
  }
}

function renderAdvancedReport(result) {
  const root = $("#advancedReport");
  const aeo = result.japanese_aeo || {};
  root.hidden = false;
  $("#aeoScore").textContent = aeo.checked ? aeo.score : "--";
  $("#aeoNotice").textContent =
    aeo.notice || "再監査すると日本語AEO判定が追加されます。";
  $("#aeoMetrics").innerHTML =
    Object.entries(aeo.metrics || {})
      .map(([key, value]) =>
        metricBox(
          aeoLabels[key] || key,
          value.score,
          key === "claim_risk" ? "低いほど安全" : "",
        ),
      )
      .join("") ||
    '<p class="muted">日本語AEOの詳細は次回の監査で計算されます。</p>';

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
      .join("") || '<p class="muted">推定値がありません。</p>';
}

function metricBox(label, value, note = "") {
  return `<div class="aeo-metric"><span>${escapeHtml(label)}</span><b>${value == null ? "--" : escapeHtml(String(value))}</b><small>${escapeHtml(note || "/ 100")}</small></div>`;
}

function renderPrompt(prompt, runs, llmReady) {
  const history = runs || [];
  const latest = history[0];
  const previous = history.slice(1, 6);
  const historyHtml = previous.length
    ? `<details class="history-details"><summary>過去の確認結果 ${previous.length}件を表示</summary>${previous.map((run) => renderRun(run)).join("")}</details>`
    : "";
  return `<div class="prompt-item"><div class="prompt-content"><p>${escapeHtml(prompt.prompt)}</p><span class="prompt-meta">登録 ${new Date(prompt.created_at).toLocaleDateString("ja-JP")}</span></div><button class="secondary" data-prompt="${prompt.id}" ${llmReady ? "" : "disabled"}>${llmReady ? "本文を読ませて確認" : "AI接続未設定"}</button>${latest ? renderRun(latest) : ""}${historyHtml}</div>`;
}

function renderRun(run) {
  const analysis = run.analysis || {};
  const score = analysis.answerability_score ?? "--";
  const columns = [
    ["確認できた根拠", analysis.supported_points],
    ["不足情報", analysis.missing_information],
    ["改善案", analysis.improvement_suggestions],
  ]
    .map(
      ([title, items]) =>
        `<div class="analysis-box"><b>${title}</b>${listHtml(items)}</div>`,
    )
    .join("");
  return `<div class="run-result"><div class="run-head"><span class="run-badge">${escapeHtml(providerName(run.provider))}</span><span class="run-badge">${escapeHtml(run.model)}</span><span class="run-score">回答可能性 ${score}点</span><span class="prompt-meta">${new Date(run.created_at).toLocaleString("ja-JP")}</span></div><p class="scope-note">${escapeHtml(analysis.notice || "旧形式の回答記録です。外部AI検索の実測ではありません。")}</p><pre class="ai-response">${escapeHtml(run.response_text || "回答なし")}</pre><div class="analysis-columns">${columns}</div></div>`;
}

function providerName(value) {
  if (value === "ollama-local") return "ローカルGemma 4";
  if (value === "ollama-rqdb4ai") return "RQDB4AI Gemma 4（0.14）";
  if (value === "deepseek") return "DeepSeek";
  return value || "LLM";
}

function listHtml(items) {
  return Array.isArray(items) && items.length
    ? `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
    : '<span class="prompt-meta">なし</span>';
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
    notice("サイトを登録しました。");
    await loadAll();
  } catch (err) {
    notice(`登録できませんでした: ${humanError(err.message)}`);
  } finally {
    button.disabled = false;
  }
});

async function runAudit() {
  if (!state.selected) return;
  const b = $("#auditButton");
  b.disabled = true;
  b.textContent = "安全に監査中…";
  notice("ページ・robots.txt・llms.txt・構造化データなどを確認しています。");
  try {
    await api(`/api/sites/${state.selected.id}/audits`, { method: "POST" });
    notice("GEO監査が完了しました。");
    await loadAll();
    state.selected = state.sites.find((s) => s.id === state.selected.id);
    await loadAudits();
  } catch (err) {
    if (err.status === 402 || err.message === "PAYMENT_REQUIRED") {
      notice("2回目以降の診断には、診断クレジットが必要です。");
      await openBilling();
      return;
    }
    notice(`監査に失敗しました: ${humanError(err.message)}`);
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
    notice("監視する質問を登録しました。");
  } catch (err) {
    notice(`登録できませんでした: ${humanError(err.message)}`);
  } finally {
    button.disabled = false;
  }
});

function humanError(v) {
  if (v === "PAYMENT_REQUIRED")
    return "2回目以降の診断には、200円または20,000 URLAIの診断クレジットが必要です。";
  if (v === "FREE_AUDIT_LIMIT_REACHED")
    return "今月の無料監査回数に達しました。";
  if (v === "FREE_MONITOR_LIMIT_REACHED")
    return "今月の無料AI確認回数に達しました。";
  return v;
}

function updateAuditButton() {
  const button = $("#auditButton");
  if (!button || button.disabled) return;
  if (state.billing?.first_free) {
    button.textContent = "初回無料でGEO監査";
  } else if ((state.billing?.credits || 0) > 0) {
    button.textContent = "クレジットでGEO監査";
  } else {
    button.textContent = "GEO監査を実行（200円 / 20,000 URLAI）";
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
  billingSay("決済情報を確認しています…");
  try {
    const info = await refreshBilling();
    $("#billingCredits").textContent = String(info.credits);
    $("#billingReceiver").textContent = info.urlai_receiver || "-";
    billingSay("支払い方法を選択してください。");
    mountPaypal();
  } catch (error) {
    billingSay(`決済情報を取得できませんでした: ${humanError(error.message)}`);
  }
}

async function billingGranted(data) {
  state.billing = { ...(state.billing || {}), credits: data.credits };
  $("#billingCredits").textContent = String(data.credits);
  $("#usage").textContent = usageText();
  billingSay(`${data.message} 診断を自動的に再開します。`, true);
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
                description: "Kurage GEO 診断1回",
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
              else billingSay(result.message || "決済を確認できませんでした。");
            } catch (error) {
              billingSay(`決済確認に失敗しました: ${humanError(error.message)}`);
            }
          }),
        onError: () =>
          billingSay("PayPal決済でエラーが発生しました。時間をおいて再試行してください。"),
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
  script.onerror = () => billingSay("PayPalの決済画面を読み込めませんでした。");
  document.head.appendChild(script);
}

async function verifyUrlai() {
  const wallet = $("#billingWallet").value.trim();
  if (!wallet) {
    billingSay("送金元ウォレットアドレスを入力してください。");
    return;
  }
  billingSay("Baseチェーン上の送金を確認しています…");
  const button = $("#billingVerifyUrlai");
  button.disabled = true;
  try {
    const result = await api("/billing/urlai", {
      method: "POST",
      body: JSON.stringify({ wallet }),
    });
    if (result.ok) await billingGranted(result);
    else billingSay(result.message || "送金を確認できませんでした。");
  } catch (error) {
    billingSay(`送金確認に失敗しました: ${humanError(error.message)}`);
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
