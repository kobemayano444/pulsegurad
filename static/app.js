let trafficChart = null;
let allowedSeries = [];
let blockedSeries = [];
let labelsSeries = [];
let pollTimer = null;

function logLine(msg) {
  const el = document.getElementById("log");
  if (!el) return;
  const now = new Date().toLocaleTimeString();
  el.textContent = `[${now}] ${msg}
` + el.textContent;
}

async function checkHealth() {
  const el = document.getElementById("health");
  if (!el) return;
  try {
    const r = await fetch("/api/health");
    if (!r.ok) throw new Error(`${r.status}`);
    el.textContent = "OK";
    el.className = "mini-v text-emerald-200";
  } catch (e) {
    el.textContent = "DOWN";
    el.className = "mini-v text-red-200";
  }
}

async function hitPing(n) {
  for (let i = 0; i < n; i++) {
    const headers = { "x-api-key": i % 2 === 0 ? "DEMO123" : "DEMO456" };
    const r = await fetch("/api/ping", { headers });
    if (r.status === 429) {
      const retryAfter = r.headers.get("Retry-After");
      logLine(`429 rate limited (retry after ${retryAfter}s) ...`);
    } else {
      const remaining = r.headers.get("X-RateLimit-Remaining");
      const algo = r.headers.get("X-RateLimit-Algorithm");
      logLine(`200 ok (remaining ${remaining}, algo ${algo})`);
    }
  }
}

async function resetMetrics() {
  try {
    await fetch("/api/admin/reset", { method: "POST" });
    logLine("Metrics reset");
    refreshMetrics();
  } catch (e) {
    logLine("Failed to reset metrics");
  }
}

function initChart() {
  const ctx = document.getElementById("trafficChart");
  if (!ctx) return;

  trafficChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labelsSeries,
      datasets: [
        {
          label: "Allowed",
          data: allowedSeries,
          tension: 0.35,
          borderWidth: 2,
        },
        {
          label: "Blocked",
          data: blockedSeries,
          tension: 0.35,
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { labels: { color: "rgba(226, 232, 240, 0.95)" } },
      },
      scales: {
        x: { ticks: { color: "rgba(148, 163, 184, 0.95)" }, grid: { color: "rgba(51, 65, 85, 0.35)" } },
        y: { ticks: { color: "rgba(148, 163, 184, 0.95)" }, grid: { color: "rgba(51, 65, 85, 0.35)" } },
      },
    },
  });
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function renderTopBlocked(items) {
  const container = document.getElementById("topBlocked");
  if (!container) return;

  if (!items || items.length === 0) {
    container.innerHTML = '<p class="text-sm text-slate-200/60">No data yet.</p>';
    return;
  }

  container.innerHTML = items
    .map(
      (x) => `
      <div class="flex items-center justify-between gap-3 p-3 rounded-xl bg-slate-900/40 ring-1 ring-slate-700/40">
        <div>
          <p class="text-sm font-semibold text-slate-100">${x.client_id}</p>
          <p class="text-xs text-slate-300/80">blocked requests</p>
        </div>
        <div class="text-lg font-bold text-red-200">${x.blocked}</div>
      </div>`
    )
    .join("");
}

async function refreshMetrics() {
  try {
    const r = await fetch("/api/metrics");
    const data = await r.json();

    setText("allowed", data.allowed);
    setText("blocked", data.blocked);
    setText("algo", data.algo);

    // update chart series (keep last 20 points)
    const t = new Date().toLocaleTimeString();
    labelsSeries.push(t);
    allowedSeries.push(data.allowed);
    blockedSeries.push(data.blocked);

    if (labelsSeries.length > 20) {
      labelsSeries.shift();
      allowedSeries.shift();
      blockedSeries.shift();
    }

    if (trafficChart) {
      trafficChart.update();
    }

    renderTopBlocked(data.top_blocked);
  } catch (e) {
    // ignore transient errors
  }
}

function startMetricsPolling() {
  if (pollTimer) clearInterval(pollTimer);
  refreshMetrics();
  pollTimer = setInterval(refreshMetrics, 2000);
}
