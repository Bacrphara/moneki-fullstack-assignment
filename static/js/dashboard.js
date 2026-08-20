const $ = (selector) => document.querySelector(selector);
const money = (value) => value == null ? "—" : new Intl.NumberFormat("zh-CN", {
  style: "currency", currency: "CNY",
}).format(value);

let sessionId;
let assistantBusy = false;
let hasUnreadAnswer = false;
let dashboardRequestId = 0;
const minimumLoadingMs = 500;
const dashboardMinimumLoadingMs = 500;
const assistantDialog = $("#assistant-dialog");
const messages = $("#messages");

function scrollMessages() {
  const behavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
  messages.scrollTo({ top: messages.scrollHeight, behavior });
}

function updateLaunchButtons() {
  const label = assistantBusy ? "正在查询…" : hasUnreadAnswer ? "查看新回答" : "问问经营助手";
  document.querySelectorAll(".assistant-launch").forEach((button) => {
    button.textContent = label;
    button.classList.toggle("has-unread", hasUnreadAnswer);
    button.setAttribute("aria-expanded", String(assistantDialog.open));
  });
}

function openAssistant() {
  if (!assistantDialog.open) assistantDialog.showModal();
  hasUnreadAnswer = false;
  updateLaunchButtons();
  requestAnimationFrame(scrollMessages);
}

function closeAssistant() {
  if (assistantDialog.open) assistantDialog.close();
  updateLaunchButtons();
}

function query() {
  return new URLSearchParams(new FormData($("#filters"))).toString();
}

async function responseJson(response, fallbackMessage) {
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error(fallbackMessage);
  }
  if (!response.ok) throw new Error(payload?.error?.message || fallbackMessage);
  return payload;
}

async function get(path) {
  const response = await fetch(`${path}${path.includes("?") ? "&" : "?"}${query()}`);
  return (await responseJson(response, "数据请求失败，请稍后重试。")).data;
}

function setDashboardStatus(state, message) {
  const status = $("#dashboard-status");
  status.className = `dashboard-status is-${state}`;
  status.querySelector(".spinner").hidden = state !== "loading";
  status.querySelector("span").textContent = message;
  const button = $("#filters button");
  button.disabled = state === "loading";
  button.textContent = state === "loading" ? "更新中…" : "更新看板";
}

function renderEmptyDashboard() {
  const emptyChart = document.createElement("p");
  emptyChart.className = "empty-state";
  emptyChart.textContent = "所选日期暂无营业额趋势";
  $("#chart").replaceChildren(emptyChart);
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = 4;
  cell.className = "empty-state";
  cell.textContent = "所选日期暂无商品销售记录";
  row.append(cell);
  $("#products").replaceChildren(row);
}

async function load() {
  const requestId = ++dashboardRequestId;
  const loadingStartedAt = performance.now();
  setDashboardStatus("loading", "正在加载看板数据…");
  try {
    const [summary, trend, products, radar] = await Promise.all([
      get("/api/dashboard/summary"), get("/api/dashboard/trend"),
      get("/api/dashboard/top-products"), get("/api/insights/radar"),
    ]);
    await new Promise((resolve) => setTimeout(resolve, Math.max(0, dashboardMinimumLoadingMs - (performance.now() - loadingStartedAt))));
    if (requestId !== dashboardRequestId) return;
    $("#revenue").textContent = money(summary.revenue);
    $("#orders").textContent = summary.orders.toLocaleString();
    $("#aov").textContent = money(summary.aov);
    const max = Math.max(...trend.map((item) => item.revenue), 1);
    $("#chart").replaceChildren(...trend.map((item) => {
      const bar = document.createElement("div");
      bar.className = "bar";
      bar.style.height = `${Math.max(3, item.revenue / max * 100)}%`;
      bar.dataset.tip = `${item.date} · ${money(item.revenue)}`;
      return bar;
    }));
    $("#products").replaceChildren(...products.map((item, index) => {
      const row = document.createElement("tr");
      for (const value of [`${index + 1}. ${item.product_name}`, item.category, item.qty, money(item.revenue)]) {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.append(cell);
      }
      return row;
    }));
    $("#radar-head").textContent = radar.headline;
    $("#signals").replaceChildren(...radar.signals.map((item) => {
      const signal = document.createElement("div");
      signal.className = "signal";
      const title = document.createElement("b");
      title.textContent = item.title;
      const detail = document.createElement("small");
      detail.textContent = item.detail;
      signal.append(title, detail);
      return signal;
    }));
    if (!trend.length) {
      renderEmptyDashboard();
      setDashboardStatus("empty", "所选日期暂无销售数据，请调整日期范围后重试。");
    } else {
      const filters = new FormData($("#filters"));
      const range = filters.get("start") && filters.get("end") ? ` · ${filters.get("start")} 至 ${filters.get("end")}` : " · 默认最近 30 天";
      setDashboardStatus("success", `看板已更新${range}`);
    }
  } catch (error) {
    await new Promise((resolve) => setTimeout(resolve, Math.max(0, dashboardMinimumLoadingMs - (performance.now() - loadingStartedAt))));
    if (requestId !== dashboardRequestId) return;
    $("#radar-head").textContent = error.message;
    setDashboardStatus("error", `${error.message} 请检查日期或稍后重试。`);
  }
}

function csrfToken() {
  return document.cookie.split("; ").find((item) => item.startsWith("csrftoken="))?.split("=")[1] || "";
}

async function ensureSession() {
  if (sessionId) return;
  const response = await fetch("/api/assistant/sessions", {
    method: "POST", headers: { "X-CSRFToken": csrfToken() },
  });
  sessionId = (await responseJson(response, "无法创建问答会话，请刷新页面后重试。")).data.session_id;
}

function setAssistantBusy(busy) {
  assistantBusy = busy;
  const status = $("#assistant-status");
  status.hidden = !busy;
  if (busy) messages.append(status);
  $("#assistant-question").disabled = busy;
  $("#chat button").disabled = busy;
  $("#chat button").textContent = busy ? "查询中…" : "发送";
  updateLaunchButtons();
  if (busy) requestAnimationFrame(scrollMessages);
}

function addMessage(className, text) {
  const message = document.createElement("div");
  message.className = className;
  message.textContent = text;
  messages.append(message);
  scrollMessages();
  return message;
}

const fieldNames = {
  product: "商品", month: "月份", start: "开始日期", end: "结束日期",
  store_id: "门店", product_id: "商品编号", revenue: "营业额", orders: "订单数",
  qty: "销量", category: "门店品类", aov: "客单价", change: "变化值", periods: "对比期间",
};

function readableValue(key, value) {
  if (value == null) return "无匹配数据";
  if (["revenue", "aov", "change"].includes(key) && typeof value === "number") return money(value);
  if (Array.isArray(value)) return value.map((item) => typeof item === "object" ? JSON.stringify(item) : item).join("；");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function evidenceList(data, traceId) {
  const list = document.createElement("dl");
  const rows = [
    ["查询工具", `${data.evidence.tool}（${data.mode === "deepseek" ? "DeepSeek 规划" : "本地可靠解析"}）`],
    ...Object.entries(data.evidence.filters || {}).map(([key, value]) => [fieldNames[key] || key, readableValue(key, value)]),
    ...Object.entries(data.evidence.result || {}).map(([key, value]) => [fieldNames[key] || key, readableValue(key, value)]),
    ["请求追踪 ID", traceId],
  ];
  for (const [label, value] of rows) {
    const term = document.createElement("dt");
    term.textContent = label;
    const description = document.createElement("dd");
    description.textContent = value;
    list.append(term, description);
  }
  return list;
}

function addAnswer(data, traceId) {
  const message = addMessage("bot", data.answer);
  const details = document.createElement("details");
  details.className = "evidence";
  const summary = document.createElement("summary");
  summary.textContent = "查看数据依据";
  details.append(summary, evidenceList(data, traceId));
  if (data.status === "answered") {
    const sync = document.createElement("button");
    sync.type = "button";
    sync.className = "sync";
    sync.textContent = "同步到看板";
    sync.addEventListener("click", () => {
      const filters = data.dashboard_filters || {};
      if (filters.start?.length === 10) $("[name=start]").value = filters.start;
      if (filters.end?.length === 10) $("[name=end]").value = filters.end;
      history.replaceState(null, "", `?${query()}`);
      closeAssistant();
      load();
    });
    details.append(sync);
  }
  message.append(details);
  scrollMessages();
}

function addError(question, error) {
  const message = addMessage("bot error", `查询失败：${error.message}`);
  const retry = document.createElement("button");
  retry.type = "button";
  retry.className = "retry";
  retry.textContent = "重试这次提问";
  retry.addEventListener("click", () => ask(question));
  message.append(retry);
  scrollMessages();
}

async function ask(question) {
  if (assistantBusy || !question.trim()) return;
  addMessage("user", question);
  const loadingStartedAt = performance.now();
  setAssistantBusy(true);
  try {
    await ensureSession();
    const response = await fetch("/api/assistant/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      body: JSON.stringify({ session_id: sessionId, question }),
    });
    const payload = await responseJson(response, "经营助手暂时无法回答，请稍后重试。");
    await new Promise((resolve) => setTimeout(resolve, Math.max(0, minimumLoadingMs - (performance.now() - loadingStartedAt))));
    addAnswer(payload.data, payload.meta.trace_id);
    if (!assistantDialog.open) {
      hasUnreadAnswer = true;
      updateLaunchButtons();
    }
  } catch (error) {
    await new Promise((resolve) => setTimeout(resolve, Math.max(0, minimumLoadingMs - (performance.now() - loadingStartedAt))));
    addError(question, error);
  } finally {
    setAssistantBusy(false);
  }
}

$("#filters").addEventListener("submit", (event) => {
  event.preventDefault();
  history.replaceState(null, "", `?${query()}`);
  load();
});

$("#chat").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = event.currentTarget.question;
  const question = input.value.trim();
  if (question) {
    input.value = "";
    ask(question);
  }
});

document.addEventListener("click", (event) => {
  if (event.target.matches(".assistant-launch")) openAssistant();
  if (event.target.matches(".prompt")) {
    event.target.classList.add("is-pressed");
    setTimeout(() => event.target.classList.remove("is-pressed"), 350);
    ask(event.target.textContent);
  }
});

$("#assistant-close").addEventListener("click", closeAssistant);
assistantDialog.addEventListener("close", updateLaunchButtons);
assistantDialog.addEventListener("click", (event) => {
  if (event.target === assistantDialog) closeAssistant();
});

const initial = new URLSearchParams(location.search);
for (const key of ["start", "end"]) {
  if (initial.get(key)) $(`[name=${key}]`).value = initial.get(key);
}
load();
