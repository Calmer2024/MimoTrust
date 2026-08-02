const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const state = {
  token: sessionStorage.getItem("mimotrustAdminToken") || "",
  config: null,
  draftId: null,
  manifest: null,
  galleryFiles: [],
  richBlocks: [{ kind: "text", text: "" }],
  richImageCounter: 0,
};

const typeSections = {
  video: "#videoFields",
  audio: "#audioFields",
  article: "#articleFields",
  rich_article: "#richFields",
  image_gallery: "#galleryFields",
};

function currentType() {
  return $('input[name="contentType"]:checked').value;
}

function setStatus(message, kind = "") {
  const element = $("#operationStatus");
  element.textContent = message;
  element.className = `operation-status ${kind}`;
}

function setConnection(message, stateName) {
  const element = $("#connectionState");
  element.textContent = message;
  element.dataset.state = stateName;
}

function setProgress(value) {
  $("#progressBar").style.width = `${Math.max(0, Math.min(100, value))}%`;
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Authorization", `Bearer ${state.token}`);
  if (options.body && typeof options.body === "string") headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...options, headers });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error?.message || `HTTP ${response.status}`);
  return body;
}

async function connect() {
  state.token = $("#adminToken").value.trim();
  sessionStorage.setItem("mimotrustAdminToken", state.token);
  setConnection("连接中", "idle");
  try {
    state.config = await api("/admin/v1/config");
    $("#storageSummary").textContent = `${state.config.bucket} / ${state.config.endpoint} / ${state.config.object_prefix}`;
    setConnection("已连接", "ok");
    updateCanonicalUrl(true);
    await refreshContents();
  } catch (error) {
    setConnection("连接失败", "error");
    setStatus(error.message, "error");
  }
}

function updateType() {
  const selected = currentType();
  Object.entries(typeSections).forEach(([type, selector]) => {
    $(selector).hidden = type !== selected;
  });
  $("#blockActions").hidden = selected !== "rich_article";
  state.draftId = null;
  state.manifest = null;
  $("#publishButton").disabled = true;
  $("#manifestPreview").textContent = "等待内容上传与校验";
}

function updateCanonicalUrl(force = false) {
  if (!state.config) return;
  const field = $("#canonicalUrl");
  if (force || !field.value || field.dataset.automatic === "true") {
    const contentId = $("#contentId").value.trim() || "content-id";
    field.value = `${state.config.canonical_base_url}/${contentId}`;
    field.dataset.automatic = "true";
  }
}

function renderRichBlocks() {
  const root = $("#richBlocks");
  root.replaceChildren();
  state.richBlocks.forEach((block, index) => {
    const row = document.createElement("div");
    row.className = "ordered-row";
    const number = document.createElement("div");
    number.className = "order-index";
    number.textContent = String(index + 1).padStart(2, "0");
    const field = document.createElement("div");
    if (block.kind === "text") {
      const textarea = document.createElement("textarea");
      textarea.rows = 4;
      textarea.value = block.text;
      textarea.setAttribute("aria-label", `文字块 ${index + 1}`);
      textarea.addEventListener("input", () => { block.text = textarea.value; });
      field.append(textarea);
    } else {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = "image/png,image/jpeg,image/webp";
      input.setAttribute("aria-label", `图片块 ${index + 1}`);
      input.addEventListener("change", () => { block.file = input.files[0] || null; });
      field.append(input);
    }
    row.append(number, field, rowActions(state.richBlocks, index, renderRichBlocks));
    root.append(row);
  });
}

function rowActions(collection, index, render) {
  const actions = document.createElement("div");
  actions.className = "row-actions";
  [
    ["↑", "上移", () => move(collection, index, -1, render)],
    ["↓", "下移", () => move(collection, index, 1, render)],
    ["×", "删除", () => { collection.splice(index, 1); render(); }],
  ].forEach(([text, title, action]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = text;
    button.title = title;
    button.setAttribute("aria-label", title);
    button.addEventListener("click", action);
    actions.append(button);
  });
  return actions;
}

function move(collection, index, delta, render) {
  const target = index + delta;
  if (target < 0 || target >= collection.length) return;
  [collection[index], collection[target]] = [collection[target], collection[index]];
  render();
}

function renderGallery() {
  const root = $("#galleryList");
  root.replaceChildren();
  state.galleryFiles.forEach((file, index) => {
    const row = document.createElement("div");
    row.className = "ordered-row";
    const number = document.createElement("div");
    number.className = "order-index";
    number.textContent = String(index + 1).padStart(2, "0");
    const name = document.createElement("div");
    name.textContent = `${file.name} · ${formatBytes(file.size)}`;
    row.append(number, name, rowActions(state.galleryFiles, index, renderGallery));
    root.append(row);
  });
}

function formatBytes(value) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function fileMime(file) {
  const extension = file.name.toLowerCase().split(".").pop();
  const byExtension = {
    mp4: "video/mp4", mp3: "audio/mpeg", m4a: "audio/mp4",
    png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", webp: "image/webp", vtt: "text/vtt",
  };
  return byExtension[extension] || file.type || "application/octet-stream";
}

function descriptor(assetId, role, file, order) {
  return {
    asset_id: assetId,
    role,
    file_name: file.name,
    mime_type: fileMime(file),
    order,
    file,
  };
}

function optionalFile(selector, assetId, role, order, assets) {
  const file = $(selector).files[0];
  if (file) assets.push(descriptor(assetId, role, file, order));
}

function collectAssets(contentId) {
  const type = currentType();
  const assets = [];
  let blocks = [];
  if (type === "video") {
    const main = $("#videoMain").files[0];
    if (!main) throw new Error("请选择 MP4 视频");
    assets.push(descriptor("video-main", "analysis", main, 0));
    optionalFile("#videoCover", "video-cover", "cover", assets.length, assets);
    optionalFile("#videoSubtitle", "video-subtitle", "subtitle", assets.length, assets);
  } else if (type === "audio") {
    const main = $("#audioMain").files[0];
    if (!main) throw new Error("请选择 MP3 或 M4A 音频");
    assets.push(descriptor("audio-main", "analysis", main, 0));
    optionalFile("#audioCover", "audio-cover", "cover", assets.length, assets);
    optionalFile("#audioSubtitle", "audio-subtitle", "subtitle", assets.length, assets);
  } else if (type === "article") {
    const body = $("#articleBody").value.trim();
    if (!body) throw new Error("请输入文章正文");
    const file = new File([body], `${contentId}.txt`, { type: "text/plain" });
    assets.push(descriptor("article-body", "analysis", file, 0));
    optionalFile("#articleCover", "article-cover", "cover", assets.length, assets);
  } else if (type === "rich_article") {
    if (!state.richBlocks.length) throw new Error("请至少添加一个图文块");
    let imageIndex = 0;
    blocks = state.richBlocks.map((block) => {
      if (block.kind === "text") {
        if (!block.text.trim()) throw new Error("图文文字块不能为空");
        return { block_type: "text", text: block.text.trim() };
      }
      if (!block.file) throw new Error("请选择图文图片");
      imageIndex += 1;
      const assetId = `image-${String(imageIndex).padStart(3, "0")}`;
      assets.push(descriptor(assetId, "analysis", block.file, assets.length));
      return { block_type: "image", asset_id: assetId };
    });
    if (!imageIndex) throw new Error("图文内容至少需要一张图片");
  } else {
    if (!state.galleryFiles.length) throw new Error("请选择至少一张图片");
    state.galleryFiles.forEach((file, index) => {
      assets.push(descriptor(`image-${String(index + 1).padStart(3, "0")}`, "analysis", file, index));
    });
  }
  return { assets, blocks };
}

function buildDraftRequest() {
  if (!$("#contentForm").reportValidity()) throw new Error("请填写所有必填字段");
  const contentId = $("#contentId").value.trim();
  const { assets, blocks } = collectAssets(contentId);
  const publishedValue = $("#publishedAt").value;
  if (!publishedValue) throw new Error("请选择发布时间");
  return {
    request: {
      content_type: currentType(),
      content_id: contentId,
      title: $("#title").value.trim(),
      author: $("#author").value.trim(),
      published_at: new Date(publishedValue).toISOString(),
      canonical_url: $("#canonicalUrl").value.trim(),
      assets: assets.map(({ file, ...asset }) => asset),
      blocks,
      display_metrics: {
        like_count: Number($("#likeCount").value),
        comment_count: Number($("#commentCount").value),
        share_count: Number($("#shareCount").value),
      },
    },
    assets,
  };
}

function uploadAsset(draftId, asset, index, total) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("PUT", `/admin/v1/drafts/${draftId}/assets/${asset.asset_id}`);
    request.setRequestHeader("Authorization", `Bearer ${state.token}`);
    request.setRequestHeader("Content-Type", "application/octet-stream");
    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) setProgress(((index + event.loaded / event.total) / total) * 85);
    });
    request.addEventListener("load", () => {
      let body = {};
      try { body = JSON.parse(request.responseText); } catch (_) {}
      if (request.status >= 200 && request.status < 300) resolve(body);
      else reject(new Error(body.error?.message || `HTTP ${request.status}`));
    });
    request.addEventListener("error", () => reject(new Error(`上传 ${asset.file.name} 失败`)));
    request.send(asset.file);
  });
}

async function prepareContent(event) {
  event.preventDefault();
  if (!state.config) {
    setStatus("请先连接管理服务", "error");
    return;
  }
  $("#prepareButton").disabled = true;
  $("#publishButton").disabled = true;
  state.manifest = null;
  try {
    const { request, assets } = buildDraftRequest();
    setStatus("正在创建草稿");
    setProgress(3);
    const draft = await api("/admin/v1/drafts", { method: "POST", body: JSON.stringify(request) });
    state.draftId = draft.draft_id;
    for (let index = 0; index < assets.length; index += 1) {
      setStatus(`正在上传 ${assets[index].file.name}`);
      await uploadAsset(state.draftId, assets[index], index, assets.length);
    }
    setStatus("正在生成 Manifest 预览");
    setProgress(90);
    const preview = await api(`/admin/v1/drafts/${state.draftId}/preview`, { method: "POST" });
    state.manifest = preview.manifest;
    $("#manifestPreview").textContent = JSON.stringify(state.manifest, null, 2);
    $("#copyManifest").disabled = false;
    $("#publishButton").disabled = false;
    setProgress(100);
    setStatus(`草稿 ${draft.content_version} 已通过校验，可以发布`, "success");
  } catch (error) {
    setProgress(0);
    setStatus(error.message, "error");
  } finally {
    $("#prepareButton").disabled = false;
  }
}

async function publishContent() {
  if (!state.draftId || !state.manifest) return;
  $("#publishButton").disabled = true;
  setStatus("正在上传 OSS 并发布 registry");
  try {
    const result = await api(`/admin/v1/drafts/${state.draftId}/publish`, { method: "POST" });
    state.manifest = result.manifest;
    $("#manifestPreview").textContent = JSON.stringify(result.manifest, null, 2);
    setStatus(`${result.content_id} ${result.content_version} 已发布`, "success");
    await refreshContents();
  } catch (error) {
    $("#publishButton").disabled = false;
    setStatus(error.message, "error");
  }
}

async function refreshContents() {
  if (!state.token) return;
  try {
    const result = await api("/admin/v1/contents");
    const root = $("#contentRows");
    root.replaceChildren();
    if (!result.contents.length) {
      const row = document.createElement("tr");
      row.innerHTML = '<td colspan="5">暂无已发布内容</td>';
      root.append(row);
      return;
    }
    result.contents.forEach((content) => {
      const row = document.createElement("tr");
      [content.display_order, content.content_id, content.content_version, content.content_type, content.status]
        .forEach((value) => {
          const cell = document.createElement("td");
          cell.textContent = value;
          row.append(cell);
        });
      root.append(row);
    });
  } catch (error) {
    setStatus(error.message, "error");
  }
}

function initialize() {
  $("#adminToken").value = state.token;
  const now = new Date(Date.now() - new Date().getTimezoneOffset() * 60000);
  $("#publishedAt").value = now.toISOString().slice(0, 16);
  $$('input[name="contentType"]').forEach((input) => input.addEventListener("change", updateType));
  $("#contentId").addEventListener("input", () => updateCanonicalUrl());
  $("#canonicalUrl").addEventListener("input", () => { $("#canonicalUrl").dataset.automatic = "false"; });
  $("#connectButton").addEventListener("click", connect);
  $("#contentForm").addEventListener("submit", prepareContent);
  $("#publishButton").addEventListener("click", publishContent);
  $("#refreshContents").addEventListener("click", refreshContents);
  $("#addTextBlock").addEventListener("click", () => {
    state.richBlocks.push({ kind: "text", text: "" });
    renderRichBlocks();
  });
  $("#addImageBlock").addEventListener("click", () => {
    state.richBlocks.push({ kind: "image", file: null });
    renderRichBlocks();
  });
  $("#galleryFiles").addEventListener("change", (event) => {
    state.galleryFiles = [...event.target.files];
    renderGallery();
  });
  $("#copyManifest").addEventListener("click", async () => {
    if (state.manifest) await navigator.clipboard.writeText(JSON.stringify(state.manifest, null, 2));
  });
  renderRichBlocks();
  updateType();
  if (state.token) connect();
}

initialize();

