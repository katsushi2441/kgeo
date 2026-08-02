const $ = (selector) => document.querySelector(selector);
const state = { sites: [], selected: null, usage: null };
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
    throw new Error(detail);
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
  const al = u.audits_limit == null ? "∞" : u.audits_limit,
    ml = u.monitor_runs_limit == null ? "∞" : u.monitor_runs_limit;
  return `今月 監査 ${u.audits_used}/${al} ・ AI確認 ${u.monitor_runs_used}/${ml}`;
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
    const [sites, usage] = await Promise.all([
      api("/api/sites"),
      api("/api/usage"),
    ]);
    state.sites = sites;
    state.usage = usage;
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

$("#auditButton").addEventListener("click", async (e) => {
  const b = e.currentTarget;
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
    notice(`監査に失敗しました: ${humanError(err.message)}`);
  } finally {
    b.disabled = false;
    b.textContent = "GEO監査を実行";
  }
});

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
  if (v === "FREE_AUDIT_LIMIT_REACHED")
    return "今月の無料監査回数に達しました。";
  if (v === "FREE_MONITOR_LIMIT_REACHED")
    return "今月の無料AI確認回数に達しました。";
  return v;
}
function escapeHtml(value) {
  const d = document.createElement("div");
  d.textContent = value;
  return d.innerHTML;
}
loadAll();
