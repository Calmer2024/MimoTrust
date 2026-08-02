const $ = (id) => document.getElementById(id);
const strategyLabels = { subtitle: "完整字幕", asr: "分段 ASR", visual: "全模态", hybrid: "音画联合", metadata: "元数据" };
const videoTypeLabels = { speech_dominant: "口播主导", text_dominant: "文字主导", event_footage: "现场事件", mixed: "多模态", low_information: "低信息", unknown: "待判断" };
const coverageStatusLabels = { structured_ready: "结构化完成", partial: "部分覆盖", needs_review: "需要复核", no_structured_information: "无结构化信息", unavailable: "不可用", metadata_only: "仅元数据", complete: "完整" };
let clock;
let refreshNext = false;
let historyByKey = {};
let currentResult = null;
let currentCacheKey = null;
let progressStarted = 0;

refreshIcons();
loadHistory();

document.querySelectorAll("[data-result-view]").forEach(tab => {
  tab.addEventListener("click", () => switchResultView(tab.dataset.resultView));
  tab.addEventListener("keydown", event => {
    if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
    event.preventDefault();
    const tabs = [...document.querySelectorAll("[data-result-view]")];
    const direction = event.key === "ArrowRight" ? 1 : -1;
    const next = tabs[(tabs.indexOf(tab) + direction + tabs.length) % tabs.length];
    switchResultView(next.dataset.resultView);
    next.focus();
  });
});

$("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  currentCacheKey = null;
  const started = performance.now();
  clearInterval(clock);
  $("workbench").hidden = false;
  $("result").classList.remove("active");
  $("error").classList.remove("active");
  $("loading").classList.add("active");
  $("submit").disabled = true;
  resetPipelineProgress(started);
  $("loading-label").textContent = "正在提交全流程任务";
  clock = setInterval(() => {
    $("timer").textContent = `${((performance.now() - started) / 1000).toFixed(1)}s`;
  }, 100);
  try {
    const route = selectInputRoute($("url").value);
    const data = route.kind === "text"
      ? await analyzeText(route.text, appendPipelineProgress)
      : await streamAnalysis({
          url: route.url,
          input_kind: "auto",
          mode: $("mode").value,
          verification_mode: $("verification-mode").value,
          refresh: refreshNext,
          verify: true
        }, appendPipelineProgress);
    render(data);
    loadHistory();
  } catch (error) {
    $("error").textContent = error.message;
    $("error").classList.add("active");
  } finally {
    refreshNext = false;
    clearInterval(clock);
    $("loading").classList.remove("active");
    $("submit").disabled = false;
  }
});

function selectInputRoute(value) {
  const text = value.trim();
  const match = text.match(/https?:\/\/[^\s]+/i);
  return match ? { kind: "url", url: text } : { kind: "text", text };
}

async function analyzeText(text, onProgress) {
  onProgress("正在理解文字材料并提取核心主张");
  const form = new FormData();
  form.append("title", "文字内容核验");
  form.append("text", text);
  form.append("verify", "true");
  form.append("verification_mode", $("verification-mode").value);
  const response = await fetch("/api/analyze/upload/stream", {
    method: "POST",
    body: form
  });
  const data = await readEventStream(response, onProgress, "文字内容分析失败");
  completePipelineProgress();
  return data;
}

async function streamAnalysis(payload, onProgress) {
  const response = await fetch("/api/analyze/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    const failure = await response.json().catch(() => ({}));
    throw new Error(failure.detail || "无法启动全流程任务");
  }
  const result = await readEventStream(response, onProgress, "无法启动全流程任务");
  completePipelineProgress();
  return result;
}

async function readEventStream(response, onProgress, failureMessage) {
  if (!response.ok) {
    const failure = await response.json().catch(() => ({}));
    throw new Error(failure.detail || failureMessage);
  }
  if (!response.body) throw new Error("浏览器不支持流式响应");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result = null;
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() || "";
    for (const frame of frames) {
      const dataText = frame.split("\n")
        .filter(line => line.startsWith("data:"))
        .map(line => line.slice(5).trimStart())
        .join("\n");
      if (!dataText) continue;
      const event = JSON.parse(dataText);
      if (event.type === "progress") onProgress(event.message);
      if (event.type === "error") throw new Error(event.message || "全流程执行失败");
      if (event.type === "result") result = event.data;
    }
    if (done) break;
  }
  if (!result) throw new Error("全流程结束但没有返回结果");
  return result;
}

function resetPipelineProgress(started) {
  progressStarted = started;
  $("pipeline-progress").innerHTML = "";
}

function appendPipelineProgress(message) {
  const items = [...$("pipeline-progress").children];
  items.forEach(item => {
    item.classList.remove("active");
    item.classList.add("completed");
  });
  const item = document.createElement("li");
  item.className = "active";
  const label = document.createElement("span");
  label.textContent = message;
  const elapsed = document.createElement("time");
  elapsed.textContent = `${((performance.now() - progressStarted) / 1000).toFixed(1)}s`;
  item.append(label, elapsed);
  $("pipeline-progress").append(item);
  $("loading-label").textContent = message;
}

function completePipelineProgress() {
  [...$("pipeline-progress").children].forEach(item => {
    item.classList.remove("active");
    item.classList.add("completed");
  });
  $("loading-label").textContent = "全流程完成";
}

function render(data) {
  currentResult = data;
  const meta = data.metadata;
  showThumbnail(meta.thumbnail);
  $("platform").textContent = meta.platform;
  $("video-title").textContent = meta.title;
  const mediaSize = meta.content_type === "image_carousel"
    ? `${meta.image_count || 0} 张图片`
    : meta.duration_seconds
      ? `${Math.round(meta.duration_seconds / 60 * 10) / 10} 分钟`
      : "时长未知";
  $("meta").textContent = [meta.uploader, mediaSize].filter(Boolean).join(" / ");
  $("strategy").textContent = `${strategyLabels[data.strategy] || data.strategy}${data.cached ? " / 缓存" : ""}`;
  $("summary").textContent = data.summary;
  $("coverage").textContent = data.coverage_note;
  $("points").innerHTML = data.key_points.map((point, i) =>
    `<div class="point"><b>${String(i + 1).padStart(2, "0")}</b><span>${escapeHtml(point)}</span></div>`
  ).join("");
  $("topics").innerHTML = data.topics.map(topic => `<span class="topic">${escapeHtml(topic)}</span>`).join("");

  const plan = data.extraction_plan || {};
  const coverage = data.coverage || {};
  const structured = data.structured_data || {
    "主题": "未识别内容主题", "主张": []
  };
  $("plan-badges").innerHTML = [
    [meta.content_type === "image_carousel" ? "images" : "video", meta.content_type === "image_carousel" ? "图文" : "视频"],
    ["scan-search", videoTypeLabels[plan.video_type] || plan.video_type || "未分类"],
    ["layers-3", plan.highest_cost_level || "—"],
    ["circle-check", coverageStatusLabels[coverage.status] || coverage.status || "未知"],
    ["fingerprint", data.verification?.case_id || "等待归档"]
  ].map(([icon, text]) => `<span class="plan-badge"><i data-lucide="${icon}" aria-hidden="true"></i>${escapeHtml(text)}</span>`).join("");

  $("coverage-grid").innerHTML = [
    ["语音", coverage.speech_percent ?? coverage.audio_percent ?? 0],
    ["全文保留", coverage.text_retention_percent ?? 0],
    ["屏幕文字", coverage.screen_text_percent ?? 0],
    ["场景", coverage.scene_percent ?? 0],
    ["发布上下文", coverage.post_context_captured ? 100 : 0]
  ].map(([name, value]) =>
    `<div class="coverage-cell"><span>${escapeHtml(name)}</span><strong>${Number(value).toFixed(1)}%</strong></div>`
  ).join("");

  const groups = [
    ["主题", [structured["主题"]].filter(Boolean)],
    ["核心主张", (structured["主张"] || []).map(
      claim => "【" + (claim["表达"] || "") + "】" + (claim["文本"] || "")
    )]
  ];
  $("structured-output").innerHTML = groups.map(([name, values]) =>
    `<section class="structured-group"><h3>${escapeHtml(name)}</h3>${
      values.length
        ? `<ul>${values.map(value => `<li>${escapeHtml(value)}</li>`).join("")}</ul>`
        : '<div class="structured-empty">暂无</div>'
    }</section>`
  ).join("");
  $("json-output").textContent = JSON.stringify(structured, null, 2);
  renderVerificationSafely(data.verification, structured);
  renderCleanedArticle(
    data.cleaned_article ||
    organizeSourceText(data.full_source_text || data.transcript || data.transcript_excerpt || "")
  );

  $("cost-ladder").innerHTML = (data.cost_trace || []).map(step =>
    `<div class="cost-step ${step.executed ? "executed" : ""}"><strong>${escapeHtml(step.level)}</strong>${escapeHtml(step.name)}<br>${escapeHtml(step.reason)}</div>`
  ).join("") || '<div class="history-empty">暂无成本记录</div>';

  $("keyframes").innerHTML = (data.keyframes || []).map(frame => {
    const texts = (frame.ocr_text || []).join(" / ") || "无关键文字";
    const observations = (frame.visual_observations || []).join(" / ");
    const position = frame.frame_type === "image_slide" ? `图片 ${frame.frame_index}` : formatTime(frame.timestamp_seconds);
    return `<div class="keyframe-row"><strong>${escapeHtml(position)}</strong> / ${escapeHtml(frame.frame_type)}<br>OCR：${escapeHtml(texts)}${observations ? `<br>画面：${escapeHtml(observations)}` : ""}</div>`;
  }).join("") || '<div class="history-empty">暂无关键帧结果</div>';

  renderPipelineTimings(data);
  renderStructuredInput(data);
  $("workbench").hidden = false;
  $("result").classList.add("active");
  const verificationStatus = data.verification?.status;
  switchResultView(verificationStatus ? "verification" : "overview");
  refreshIcons();
  $("content-scroll").scrollTo({ top: 0, behavior: "smooth" });
}

function showThumbnail(source) {
  const thumbnail = $("thumbnail");
  const placeholder = $("thumbnail-placeholder");
  const showPlaceholder = () => {
    thumbnail.hidden = true;
    placeholder.hidden = false;
  };
  thumbnail.onerror = showPlaceholder;
  if (!source) {
    thumbnail.removeAttribute("src");
    showPlaceholder();
    return;
  }
  placeholder.hidden = true;
  thumbnail.hidden = false;
  thumbnail.src = source;
}

function fullPipelineMilliseconds(data) {
  const extraction = Number(data.extraction_milliseconds) ||
    (data.timings || []).reduce((total, item) => total + Number(item.milliseconds || 0), 0);
  const verification = Number(data.verification?.timings?.total_seconds || 0) * 1000;
  return Number(data.full_pipeline_milliseconds) || Math.round(extraction + verification);
}

function renderStructuredInput(data) {
  const inputText = data.structured_input_text || data.full_source_text || "";
  const inputChars = Number(data.structured_input_chars) || inputText.length;
  const usedFallback = !data.structured_input_text && Boolean(data.full_source_text);
  const notes = [
    `实际输入 ${inputChars} 字符`,
    data.structured_input_truncated ? "已达到服务端输入上限，后续内容未发送" : "未截断",
    usedFallback ? "历史缓存：根据完整原文还原" : "服务端记录的实际结构化输入"
  ];
  $("llm-structured-input-meta").textContent = notes.join(" · ");
  $("llm-structured-input").textContent = inputText || "当前记录没有可展示的结构化模型输入";
}

function renderPipelineTimings(data) {
  const extractionMilliseconds = Number(data.extraction_milliseconds) ||
    (data.timings || []).reduce((total, item) => total + Number(item.milliseconds || 0), 0);
  const verificationMilliseconds = Math.round(Number(data.verification?.timings?.total_seconds || 0) * 1000);
  const totalMilliseconds = fullPipelineMilliseconds(data);
  const extractionTraceItems = (data.timings || []).map(item => ({
    phase: "信息提取", name: item.name, milliseconds: Number(item.milliseconds || 0), kind: "extraction"
  }));
  const verificationTraceItems = Object.entries(data.verification?.timings?.stages || {}).map(([name, seconds]) => ({
    phase: "信源核实", name: stageLabel(name), milliseconds: Math.round(Number(seconds || 0) * 1000), kind: "verification"
  }));
  const traceItems = [...extractionTraceItems, ...verificationTraceItems];
  const traceHtml = traceItems.map(item =>
    `<div class="trace-item trace-${item.kind}"><span>${escapeHtml(item.phase)} · ${escapeHtml(item.name)}</span><strong>${formatDuration(item.milliseconds)}</strong></div>`
  ).join("");
  const totalsHtml = `<div class="trace-item trace-total"><span>全流程 · 总时长</span><strong>${formatDuration(totalMilliseconds)}</strong></div>`;
  $("trace").innerHTML = traceHtml + totalsHtml;
  $("process-trace").innerHTML = traceHtml + totalsHtml;
  $("full-pipeline-summary").innerHTML = [
    ["信息提取", extractionMilliseconds],
    ["信源核实", verificationMilliseconds],
    ["全流程", totalMilliseconds]
  ].map(([label, milliseconds], index) => `<div class="pipeline-summary-item ${index === 2 ? "primary" : ""}"><span>${escapeHtml(label)}</span><strong>${formatDuration(milliseconds)}</strong></div>`).join("");
}

function renderVerificationSafely(verification, structured) {
  const requiredContainers = [
    "trust-hero", "narrative-analysis", "claim-checks", "evidence-gaps",
    "report-evidence", "report-json", "trust-audit-body"
  ];
  if (requiredContainers.some(id => !$(id))) {
    console.error("[MiMo Trust] 页面资源版本不一致，缺少信源核实容器");
    return;
  }
  try {
    renderVerification(verification, structured);
  } catch (error) {
    console.error("[MiMo Trust] 信源核实结果渲染失败", error);
    $("trust-hero").innerHTML = `<div class="trust-empty-state">
      <span class="verdict-mark verdict-error"><i data-lucide="triangle-alert" aria-hidden="true"></i></span>
      <div><p class="trust-kicker">结果展示失败</p><h2>核验数据已返回，但页面无法解析</h2>
      <button class="secondary-button" type="button" onclick="window.location.reload()"><i data-lucide="refresh-cw" aria-hidden="true"></i>刷新页面资源</button></div>
    </div>`;
    $("claim-checks").innerHTML = '<div class="history-empty">请刷新页面后重试</div>';
    $("narrative-analysis").innerHTML = '<div class="history-empty">请刷新页面后重试</div>';
    $("evidence-gaps").innerHTML = '<div class="history-empty">请刷新页面后重试</div>';
    $("report-evidence").innerHTML = '<div class="history-empty">请刷新页面后重试</div>';
    $("report-json").textContent = "";
    $("trust-audit-body").innerHTML = '<div class="history-empty">当前没有可展示的信源审计记录</div>';
  }
}

function normalizeReportSource(source) {
  return {
    id: source?.["证据编号"] || source?.id || "",
    title: source?.["标题"] || source?.title || "",
    url: source?.["链接"] || source?.url || "",
    published_date: source?.["发布日期"] || source?.published_date || "",
    author: source?.["作者"] || source?.author || "",
    relation: source?.["关系"] || source?.relation || "",
    snippet: source?.snippet || ""
  };
}

function clearVerificationReport(message) {
  $("narrative-analysis").innerHTML = `<div class="history-empty">${escapeHtml(message)}</div>`;
  $("claim-checks").innerHTML = '<div class="history-empty">暂无逐项结论</div>';
  $("evidence-gaps").innerHTML = '<div class="history-empty">暂无待补证据</div>';
  $("report-evidence").innerHTML = '<div class="history-empty">暂无关键依据</div>';
  $("report-json").textContent = "";
  $("trust-audit-body").innerHTML = '<div class="history-empty">当前没有可展示的信源审计记录</div>';
}

function renderVerification(verification, structured) {
  if (verification?.status === "skipped") {
    const message = verification.message || "当前内容没有需要外部核验的现实世界主张。";
    $("trust-hero").innerHTML = `<div class="trust-empty-state verdict-positive">
      <span class="verdict-mark"><i data-lucide="circle-check" aria-hidden="true"></i></span>
      <div><p class="trust-kicker">无需进入事实核验</p><h2>${escapeHtml(message)}</h2></div>
    </div>`;
    clearVerificationReport("本次内容已在主张提取阶段结束，不执行检索与报告生成。请在结构化数据中查看提取结果。");
    refreshIcons();
    return;
  }
  if (!verification || verification.status === "failed") {
    const failed = verification?.status === "failed";
    const message = verification?.message || "当前结果尚未执行信源核实。";
    $("trust-hero").innerHTML = `<div class="trust-empty-state">
      <span class="verdict-mark ${failed ? "verdict-error" : "verdict-pending"}"><i data-lucide="${failed ? "triangle-alert" : "search-check"}" aria-hidden="true"></i></span>
      <div><p class="trust-kicker">${failed ? "核验未完成" : "等待核验"}</p><h2>${escapeHtml(message)}</h2>
      <button class="secondary-button" type="button" onclick="retryVerification()"><i data-lucide="${failed ? "refresh-cw" : "search-check"}" aria-hidden="true"></i>${failed ? "重试信源核实" : "开始信源核实"}</button></div>
    </div>`;
    clearVerificationReport(message);
    refreshIcons();
    return;
  }

  const report = verification.report || {};
  const rawChecks = Array.isArray(report["主张核验"]) ? report["主张核验"] : [];
  const checks = rawChecks.length ? rawChecks : (verification.claim_checks || []);
  const evidence = (verification.evidence_used || []).map(normalizeReportSource);
  const reportEvidence = Array.isArray(report["关键证据"])
    ? report["关键证据"].map(normalizeReportSource)
    : [];
  const claimEvidence = checks.flatMap(check =>
    (check["依据"] || []).map(normalizeReportSource)
  );
  const evidenceById = Object.fromEntries(
    [...evidence, ...claimEvidence, ...reportEvidence]
      .filter(item => item.id)
      .map(item => [item.id, item])
  );
  const verdictClass = verdictTone(verification.overall_verdict);
  $("trust-hero").innerHTML = `<div class="trust-verdict ${verdictClass}">
    <span class="verdict-mark"><i data-lucide="${verdictIcon(verification.overall_verdict)}" aria-hidden="true"></i></span>
    <div class="trust-verdict-copy"><p class="trust-kicker">综合判定</p><h2>${escapeHtml(verification.overall_verdict || "证据不足")}</h2>
      ${report["主题"] ? `<p class="report-topic">${escapeHtml(report["主题"])}</p>` : ""}
      <p>${escapeHtml(verification.conclusion || "核验已完成。")}</p>
      ${verification.sharing_advice ? `<p class="sharing-advice"><strong>传播建议</strong>${escapeHtml(verification.sharing_advice)}</p>` : ""}</div>
    <div class="trust-stats"><div><strong>${checks.length}</strong><span>项主张</span></div><div><strong>${Number(verification.evidence_reviewed_count || 0)}</strong><span>条已审阅</span></div><div><strong>${Number(verification.evidence_selected_count || 0)}</strong><span>条入选</span></div></div>
  </div>`;

  const narrative = report["叙事分析"] || {
    "判断": verification.narrative_analysis?.verdict,
    "方式": verification.narrative_analysis?.methods,
    "说明": verification.narrative_analysis?.explanation
  };
  const narrativeMethods = Array.isArray(narrative["方式"]) ? narrative["方式"] : [];
  $("narrative-analysis").innerHTML = `<div class="narrative-summary">
    <div class="narrative-verdict"><span>判断</span><strong>${escapeHtml(narrative["判断"] || "未单独判断")}</strong></div>
    <p>${escapeHtml(narrative["说明"] || "没有额外叙事分析。")}</p>
    ${narrativeMethods.length ? `<div class="narrative-methods">${narrativeMethods.map(item => `<span>${escapeHtml(item)}</span>`).join("")}</div>` : ""}
  </div>`;

  $("claim-checks").innerHTML = checks.map(check => {
    const sourceRows = Array.isArray(check["依据"])
      ? check["依据"].map(normalizeReportSource)
      : (check.source_ids || []).map(id => evidenceById[id]).filter(Boolean);
    const claimId = check["主张编号"] || check.claim_id || "";
    const category = check["表达"] || check.category || "";
    const verdict = check["结论"] || check.verdict || "待核实";
    const claim = check["主张文本"] || check.claim || "";
    const sufficiency = check["证据充分度"] || check.evidence_sufficiency || "未说明";
    const basis = check["说明"] || check.basis || "";
    const uncertainty = check["不确定性"] || check.uncertainty || "";
    return `<article class="claim-card">
      <div class="claim-card-head"><span class="claim-id">${escapeHtml(claimId)}</span><span class="claim-category">${escapeHtml(category)}</span><span class="claim-verdict ${verdictTone(verdict)}">${escapeHtml(verdict)}</span></div>
      <h3>${escapeHtml(claim)}</h3>
      <div class="claim-detail"><span>证据充分度</span><strong>${escapeHtml(sufficiency)}</strong></div>
      <p class="claim-basis">${escapeHtml(basis)}</p>
      ${uncertainty ? `<div class="claim-uncertainty"><strong>不确定性</strong><span>${escapeHtml(uncertainty)}</span></div>` : ""}
      ${sourceRows.length ? `<div class="claim-sources">${sourceRows.map(source => sourceLink(source, true)).join("")}</div>` : '<div class="claim-no-source">本项没有引用具体证据</div>'}
    </article>`;
  }).join("") || '<div class="history-empty">没有可展示的逐项结论</div>';

  const evidenceGaps = Array.isArray(report["待补证据"])
    ? report["待补证据"]
    : (verification.evidence_gaps || []);
  $("evidence-gaps").innerHTML = evidenceGaps.length
    ? `<ol class="evidence-gap-list">${evidenceGaps.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ol>`
    : '<div class="report-empty"><i data-lucide="circle-check" aria-hidden="true"></i><span>报告未列出待补证据</span></div>';

  const criticalEvidence = reportEvidence.length
    ? reportEvidence
    : [...new Set((verification.source_ids || []).map(id => evidenceById[id]).filter(Boolean))];
  $("report-evidence").innerHTML = criticalEvidence.map(source => {
    const metadata = [source.id, source.author, source.published_date].filter(Boolean);
    return `<article class="evidence-card">
      <div class="evidence-meta">${metadata.map(item => `<span>${escapeHtml(item)}</span>`).join("")}</div>
      <h3>${sourceLink(source, false)}</h3>
      ${source.snippet ? `<p>${escapeHtml(source.snippet)}</p>` : ""}
    </article>`;
  }).join("") || '<div class="history-empty">最终报告没有列出关键依据。</div>';

  $("report-json").textContent = JSON.stringify(
    Object.keys(report).length ? report : verification,
    null,
    2
  );

  const timing = verification.timings || {};
  const stages = timing.stages || {};
  const plan = verification.search_plan || {};
  $("trust-audit-body").innerHTML = `<div class="audit-metrics">
    ${Object.entries(stages).map(([name, seconds]) => `<div><span>${escapeHtml(stageLabel(name))}</span><strong>${Number(seconds).toFixed(2)}s</strong></div>`).join("")}
    <div><span>总耗时</span><strong>${Number(timing.total_seconds || 0).toFixed(2)}s</strong></div>
  </div>
  <div class="audit-block"><h3>检索计划</h3><p>${escapeHtml(plan.reasoning || "使用保底检索计划")}</p><ol>${(plan.web_queries || []).map(query => `<li>${escapeHtml(query)}</li>`).join("")}</ol></div>
  <div class="audit-foot">案例 ${escapeHtml(verification.case_id)} · 运行 ${escapeHtml(verification.run_id)}</div>`;
}

async function retryVerification() {
  if (!currentResult?.structured_data) return;
  $("trust-hero").innerHTML = '<div class="trust-empty-state"><span class="spinner" aria-hidden="true"></span><div><p class="trust-kicker">正在重新核验</p><h2>检索并评估多源证据</h2></div></div>';
  try {
    const response = await fetch("/api/verify", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ structured_data: currentResult.structured_data, verification_mode: $("verification-mode").value, cache_key: currentCacheKey }) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "核验失败");
    currentResult.verification = data;
    renderVerification(data, currentResult.structured_data);
    if (currentCacheKey) loadHistory();
  } catch (error) {
    renderVerification({ status: "failed", message: error.message }, currentResult.structured_data);
  }
  refreshIcons();
}

function sourceLink(source, compact) {
  const url = /^https?:\/\//i.test(source.url || "") ? source.url : "";
  const relation = source.relation ? ` · ${source.relation}` : "";
  const label = compact ? `${source.id}${relation} · ${source.title || source.url}` : (source.title || source.url || source.id);
  return url ? `<a href="${escapeAttribute(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}<i data-lucide="external-link" aria-hidden="true"></i></a>` : `<span>${escapeHtml(label)}</span>`;
}

function verdictTone(verdict) {
  if (["可信", "大体可信", "属实", "大体属实"].includes(verdict)) return "verdict-positive";
  if (["不实", "误导"].includes(verdict)) return "verdict-negative";
  if (["真假混合", "部分属实"].includes(verdict)) return "verdict-mixed";
  return "verdict-pending";
}

function verdictIcon(verdict) {
  if (["可信", "大体可信", "属实", "大体属实"].includes(verdict)) return "badge-check";
  if (["不实", "误导"].includes(verdict)) return "badge-x";
  if (["真假混合", "部分属实"].includes(verdict)) return "circle-dot-dashed";
  return "circle-help";
}

function stageLabel(name) {
  return ({
    M1: "M1 输入规范化", M2: "M2 检索规划", M3: "M3 并发检索",
    M4: "M4 证据归一化", M5: "M5 证据初筛",
    M6: "M6 最终研判", M7: "M7 报告渲染"
  })[name] || name;
}

function formatDuration(milliseconds) {
  const value = Math.max(0, Number(milliseconds) || 0);
  if (value < 1000) return `${Math.round(value)} ms`;
  if (value < 60000) return `${(value / 1000).toFixed(value < 10000 ? 2 : 1)}s`;
  const minutes = Math.floor(value / 60000);
  const seconds = Math.round((value % 60000) / 1000);
  return `${minutes}m ${String(seconds).padStart(2, "0")}s`;
}

async function loadHistory() {
  try {
    const response = await fetch("/api/videos");
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "读取失败");
    if (!data.items.length) {
      historyByKey = {};
      $("history-list").innerHTML = '<div class="history-empty">暂无提取记录</div>';
      return;
    }
    historyByKey = Object.fromEntries(data.items.map(item => [item.cache_key, item.result]));
    $("history-list").innerHTML = data.items.map(item => {
      const result = item.result;
      const date = new Date(item.created_at).toLocaleString("zh-CN");
      const coverage = result.coverage || {};
      const verdict = result.verification?.overall_verdict;
      return `<div class="history-item">
        <div>
          <p class="history-title">${escapeHtml(result.metadata.title)}</p>
          <div class="history-meta">${escapeHtml(result.metadata.platform)} / ${escapeHtml(strategyLabels[result.strategy] || result.strategy)} / ${escapeHtml(coverageStatusLabels[coverage.status] || coverage.status || "未知")}${verdict ? ` / 核验：${escapeHtml(verdict)}` : " / 待核验"} / ${escapeHtml(result.verification?.verification_mode || "speed")} / ${escapeHtml(result.verification?.case_id || "unstructured")} / ${escapeHtml(date)}${item.expired ? " / 已过期" : ""}</div>
        </div>
        <div class="history-actions">
          <button type="button" onclick="viewStored('${item.cache_key}')"><i data-lucide="eye" aria-hidden="true"></i>查看</button>
          <button type="button" onclick="reanalyze('${item.cache_key}', '${encodeURIComponent(result.metadata.webpage_url)}')"><i data-lucide="rotate-ccw" aria-hidden="true"></i>重跑</button>
          <button class="delete-button" type="button" aria-label="删除记录" title="删除" onclick="deleteVideo('${item.cache_key}')"><i data-lucide="trash-2" aria-hidden="true"></i></button>
        </div>
      </div>`;
    }).join("");
    refreshIcons();
  } catch (error) {
    $("history-list").innerHTML = `<div class="history-empty">${escapeHtml(error.message)}</div>`;
  }
}

async function deleteVideo(cacheKey) {
  if (!window.confirm("删除这条记录？")) return;
  const response = await fetch(`/api/videos/${encodeURIComponent(cacheKey)}`, { method: "DELETE" });
  if (response.ok) loadHistory();
}

function viewStored(cacheKey) {
  const result = historyByKey[cacheKey];
  if (!result) return;
  currentCacheKey = cacheKey;
  $("url").value = result.metadata.webpage_url;
  $("verification-mode").value = result.verification?.verification_mode || "speed";
  render({ ...result, cached: true });
}

function reanalyze(cacheKey, encodedUrl) {
  $("url").value = decodeURIComponent(encodedUrl);
  refreshNext = true;
  $("form").requestSubmit();
}

$("clear-history").addEventListener("click", async () => {
  if (!window.confirm("清空全部缓存？")) return;
  const response = await fetch("/api/videos", { method: "DELETE" });
  if (response.ok) {
    $("result").classList.remove("active");
    $("workbench").hidden = true;
    loadHistory();
  }
});

function switchResultView(name) {
  document.querySelectorAll("[data-result-view]").forEach(tab => {
    const active = tab.dataset.resultView === name;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
  });
  document.querySelectorAll("[data-view-panel]").forEach(panel => {
    const active = panel.dataset.viewPanel === name;
    panel.hidden = !active;
    panel.classList.toggle("active", active);
  });
}

function renderCleanedArticle(article) {
  if (!article.trim()) {
    $("cleaned-article").innerHTML = '<div class="article-empty">暂无可整理的全文</div>';
    return;
  }
  const sections = article.split(/\n{2,}/).map(item => item.trim()).filter(Boolean);
  $("cleaned-article").innerHTML = sections.map(section => {
    const lines = section.split("\n").map(item => item.trim()).filter(Boolean);
    const hasHeading = lines.length > 1 && lines[0].length <= 20 && !/[。！？!?]$/.test(lines[0]);
    const heading = hasHeading ? `<h3>${escapeHtml(lines.shift())}</h3>` : "";
    const paragraphs = lines.length ? lines : [section];
    return `<section class="article-section">${heading}${paragraphs.map(
      paragraph => `<p>${escapeHtml(paragraph)}</p>`
    ).join("")}</section>`;
  }).join("");
}

function organizeSourceText(source) {
  const seen = new Set();
  const lines = source.split(/\r?\n/).map(line => line
    .replace(/^(?:\[[^\]]+\])+\s*/, "")
    .replace(/^\[?\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d+)?\]?\s*/, "")
    .replace(/^(?:标题|作者)：\s*/, "")
    .replace(/^简介：\s*/, "")
    .trim()
  ).filter(line => {
    const key = line.replace(/[\s，。！？、；：,.!?;:]+/g, "").toLowerCase();
    if (key.length < 4 || seen.has(key) || line.endsWith("...") || line.endsWith("…")) return false;
    seen.add(key);
    return true;
  });
  return lines.join("\n\n");
}

function refreshIcons() {
  if (window.lucide?.createIcons) {
    window.lucide.createIcons();
  }
}

function escapeHtml(value) {
  const node = document.createElement("div");
  node.textContent = value ?? "";
  return node.innerHTML;
}

function escapeAttribute(value) {
  return escapeHtml(value).replace(/`/g, "&#96;");
}

function formatTime(seconds) {
  const value = Math.max(0, Math.floor(Number(seconds) || 0));
  const hours = String(Math.floor(value / 3600)).padStart(2, "0");
  const minutes = String(Math.floor(value % 3600 / 60)).padStart(2, "0");
  const remain = String(value % 60).padStart(2, "0");
  return `${hours}:${minutes}:${remain}`;
}
