const $ = (selector) => document.querySelector(selector);
const money = (value) => value == null ? "—" : new Intl.NumberFormat("zh-CN", {
  style: "currency", currency: "CNY",
}).format(value);

let sessionId;
let assistantBusy = false;

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

async function load() {
  try {
    const [summary, trend, products, radar] = await Promise.all([
      get("/api/dashboard/summary"), get("/api/dashboard/trend"),
      get("/api/dashboard/top-products"), get("/api/insights/radar"),
    ]);
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
  } catch (error) {
    $("#radar-head").textContent = error.message;
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
  $("#assistant-status").hidden = !busy;
  $("#assistant-question").disabled = busy;
  $("#chat button").disabled = busy;
  $("#chat button").textContent = busy ? "查询中…" : "发送";
}

function addMessage(className, text) {
  const message = document.createElement("div");
  message.className = className;
  message.textContent = text;
  $("#messages").append(message);
  $("#messages").scrollTop = $("#messages").scrollHeight;
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
      load();
    });
    details.append(sync);
  }
  message.append(details);
}

function addError(question, error) {
  const message = addMessage("bot error", `查询失败：${error.message}`);
  const retry = document.createElement("button");
  retry.type = "button";
  retry.className = "retry";
  retry.textContent = "重试这次提问";
  retry.addEventListener("click", () => ask(question));
  message.append(retry);
}

async function ask(question) {
  if (assistantBusy || !question.trim()) return;
  addMessage("user", question);
  setAssistantBusy(true);
  try {
    await ensureSession();
    const response = await fetch("/api/assistant/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      body: JSON.stringify({ session_id: sessionId, question }),
    });
    const payload = await responseJson(response, "经营助手暂时无法回答，请稍后重试。");
    addAnswer(payload.data, payload.meta.trace_id);
  } catch (error) {
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
  if (event.target.matches(".prompt")) ask(event.target.textContent);
});

const initial = new URLSearchParams(location.search);
for (const key of ["start", "end"]) {
  if (initial.get(key)) $(`[name=${key}]`).value = initial.get(key);
}
load();
