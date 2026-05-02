const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const statusDiv = document.getElementById('status');
const envDiv = document.getElementById('env');
const resourcesDiv = document.getElementById('resources');
const pricingDiv = document.getElementById('pricing');
const vmListDiv = document.getElementById('vmList');
const actionMsg = document.getElementById('actionMsg');
const bannerDiv = document.getElementById('banner');
const hostCpu = document.getElementById('hostCpu');
const hostMemory = document.getElementById('hostMemory');
const hostDisk = document.getElementById('hostDisk');
const hostCpuBar = document.getElementById('hostCpuBar');
const hostMemoryBar = document.getElementById('hostMemoryBar');
const hostDiskBar = document.getElementById('hostDiskBar');
const alertsList = document.getElementById('alertsList');
const webhookList = document.getElementById('webhookList');
const webhookAdd = document.getElementById('webhookAdd');
const webhookName = document.getElementById('webhookName');
const webhookUrl = document.getElementById('webhookUrl');
const chartSubtitle = document.getElementById('chartSubtitle');
const chartRanges = document.getElementById('chartRanges');
const hostUsageChartCanvas = document.getElementById('hostUsageChart');
const hostNetworkChartCanvas = document.getElementById('hostNetworkChart');
const vmUsageChartCanvas = document.getElementById('vmUsageChart');
const vmNetworkChartCanvas = document.getElementById('vmNetworkChart');
const hostUsageEmpty = document.getElementById('hostUsageEmpty');
const hostNetworkEmpty = document.getElementById('hostNetworkEmpty');
const vmUsageEmpty = document.getElementById('vmUsageEmpty');
const vmNetworkEmpty = document.getElementById('vmNetworkEmpty');

const API = (window.config && window.config.apiBaseUrl) || 'http://127.0.0.1:7466/api/v1';

function fmtRes(avail, total) {
  const a = avail || {}; const t = total || {};
  return `CPU ${a.cpu ?? '?'} / ${t.cpu ?? '?'} • RAM ${a.memory ?? '?'}GB / ${t.memory ?? '?'}GB • Disk ${a.storage ?? '?'}GB / ${t.storage ?? '?'}GB`;
}

function fmtPricing(p) {
  if (!p) return '—';
  const usd = `USD: CPU $${p.usd_per_core_month}/core, RAM $${p.usd_per_gb_ram_month}/GB, Disk $${p.usd_per_gb_storage_month}/GB`;
  const glm = `GLM: CPU ${p.glm_per_core_month}/core, RAM ${p.glm_per_gb_ram_month}/GB, Disk ${p.glm_per_gb_storage_month}/GB`;
  return `${usd}\n${glm}`;
}

let monitoring = null;
let selectedVmId = null;
let chartRange = '1h';
const charts = {};

function pct(value) {
  const n = Number(value && value.value != null ? value.value : value);
  if (!Number.isFinite(n)) return null;
  return Math.max(0, Math.min(100, n));
}

function renderHostMetric(el, bar, sample) {
  const value = pct(sample);
  el.textContent = value == null ? '—' : `${value.toFixed(0)}%`;
  bar.style.width = `${value == null ? 0 : value}%`;
}

function renderVMs(vms) {
  vmListDiv.innerHTML = '';
  const list = Array.isArray(vms) ? vms : [];
  if (list.length === 0) {
    selectedVmId = null;
    const empty = document.createElement('div');
    empty.className = 'vm-row';
    empty.textContent = 'No VMs running';
    vmListDiv.appendChild(empty);
    return;
  }
  if (!selectedVmId || !list.some(vm => vm.id === selectedVmId)) {
    selectedVmId = list[0].id;
  }
  list.forEach((vm, idx) => {
    const row = document.createElement('div');
    row.className = 'vm-row';
    const radio = document.createElement('input');
    radio.type = 'radio';
    radio.name = 'vmSelect';
    radio.value = vm.id;
    radio.checked = vm.id === selectedVmId;
    radio.addEventListener('change', () => {
      selectedVmId = vm.id;
      fetchCharts();
    });
    const id = document.createElement('div');
    id.className = 'vm-id';
    id.textContent = vm.id;
    const status = document.createElement('div');
    const pill = document.createElement('span');
    pill.className = 'pill ' + ((vm.status || '').toLowerCase() === 'running' ? 'running' : 'stopped');
    pill.textContent = (vm.status || '').toUpperCase() || 'UNKNOWN';
    status.appendChild(pill);
    const res = document.createElement('div');
    res.className = 'small';
    const r = vm.resources || {};
    res.textContent = `CPU ${r.cpu ?? '—'}, RAM ${r.memory ?? '—'}GB, Disk ${r.storage ?? '—'}GB`;
    const metrics = document.createElement('div');
    metrics.className = 'small';
    const vmMetrics = monitoring && monitoring.vms && monitoring.vms[vm.id];
    const guest = vmMetrics && vmMetrics.guest_agent;
    if (guest && guest.cpu_percent) {
      const cpu = pct(guest.cpu_percent);
      const mem = pct(guest.memory_percent);
      const disk = pct(guest.disk_percent);
      metrics.textContent = `CPU ${cpu == null ? '—' : cpu.toFixed(0) + '%'} • RAM ${mem == null ? '—' : mem.toFixed(0) + '%'} • Disk ${disk == null ? '—' : disk.toFixed(0) + '%'}`;
    } else {
      metrics.innerHTML = '<span class="pill warn">Guest metrics unavailable</span>';
    }
    row.appendChild(radio);
    row.appendChild(id);
    row.appendChild(status);
    row.appendChild(res);
    row.appendChild(metrics);
    vmListDiv.appendChild(row);
  });
}

function renderAlerts(alerts) {
  const list = Array.isArray(alerts) ? alerts : [];
  alertsList.innerHTML = '';
  if (!list.length) {
    alertsList.innerHTML = '<div class="small">No active alerts.</div>';
    return;
  }
  list.forEach(alert => {
    const row = document.createElement('div');
    row.className = 'alert-row';
    row.innerHTML = `
      <span class="pill ${alert.severity === 'critical' ? 'critical' : 'warn'}">${(alert.severity || 'warning').toUpperCase()}</span>
      <div><strong>${alert.name || alert.metric}</strong><div class="small">${alert.vm_id || 'provider'} • value ${alert.last_value ?? '—'}</div></div>
      <div class="small">${alert.fired_at ? new Date(alert.fired_at).toLocaleTimeString() : ''}</div>
    `;
    alertsList.appendChild(row);
  });
}

async function fetchMonitoring() {
  try {
    const resp = await fetch(`${API}/monitoring/overview`, { cache: 'no-store' });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    monitoring = {};
    (data.vms || []).forEach(vm => { monitoring.vms = { ...(monitoring.vms || {}), [vm.id]: vm.metrics || {} }; });
    renderHostMetric(hostCpu, hostCpuBar, data.host && data.host.cpu_percent);
    renderHostMetric(hostMemory, hostMemoryBar, data.host && data.host.memory_percent);
    renderHostMetric(hostDisk, hostDiskBar, data.host && data.host.disk_percent);
    renderAlerts(data.active_alerts);
  } catch {
    monitoring = null;
    hostCpu.textContent = '—'; hostCpuBar.style.width = '0%';
    hostMemory.textContent = '—'; hostMemoryBar.style.width = '0%';
    hostDisk.textContent = '—'; hostDiskBar.style.width = '0%';
    if (alertsList) alertsList.innerHTML = '<div class="small">Monitoring unavailable.</div>';
  }
}

async function fetchHistory(scope, extra = {}) {
  const params = new URLSearchParams({ scope, range: chartRange });
  Object.entries(extra).forEach(([key, value]) => {
    if (value != null && value !== '') params.set(key, value);
  });
  const resp = await fetch(`${API}/monitoring/metrics/history?${params.toString()}`, { cache: 'no-store' });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

async function fetchCharts() {
  if (!window.Chart) return;
  try {
    const [hostHistory, vmHistory] = await Promise.all([
      fetchHistory('host'),
      selectedVmId ? fetchHistory('vm', { vm_id: selectedVmId }) : Promise.resolve({ samples: [] }),
    ]);
    renderHistoryCharts(hostHistory.samples || [], vmHistory.samples || []);
    if (chartSubtitle) {
      chartSubtitle.textContent = selectedVmId ? `Host and ${selectedVmId}` : 'Host metrics';
    }
  } catch {
    showEmpty(hostUsageChartCanvas, hostUsageEmpty, true);
    showEmpty(hostNetworkChartCanvas, hostNetworkEmpty, true);
    showEmpty(vmUsageChartCanvas, vmUsageEmpty, true);
    showEmpty(vmNetworkChartCanvas, vmNetworkEmpty, true);
  }
}

function renderHistoryCharts(hostSamples, vmSamples) {
  const hostUsage = percentSeries(hostSamples, 'infrastructure', {
    cpu_percent: 'CPU',
    memory_percent: 'RAM',
    disk_percent: 'Disk',
  });
  const hostNetwork = rateSeries(hostSamples, 'infrastructure', {
    network_rx_bytes: 'RX',
    network_tx_bytes: 'TX',
  });
  const vmUsage = percentSeries(vmSamples, 'guest_agent', {
    cpu_percent: 'CPU',
    memory_percent: 'RAM',
    disk_percent: 'Disk',
  });
  const vmNetworkGuest = rateSeries(vmSamples, 'guest_agent', {
    network_rx_bytes: 'RX',
    network_tx_bytes: 'TX',
  });
  const vmNetworkInfra = rateSeries(vmSamples, 'infrastructure', {
    proxy_rx_bytes: 'Proxy RX',
    proxy_tx_bytes: 'Proxy TX',
  });
  const vmNetwork = vmNetworkGuest.labels.length > 0 ? vmNetworkGuest : vmNetworkInfra;

  renderChart('hostUsage', hostUsageChartCanvas, hostUsageEmpty, hostUsage, percentFormatter);
  renderChart('hostNetwork', hostNetworkChartCanvas, hostNetworkEmpty, hostNetwork, rateFormatter);
  renderChart('vmUsage', vmUsageChartCanvas, vmUsageEmpty, vmUsage, percentFormatter);
  renderChart('vmNetwork', vmNetworkChartCanvas, vmNetworkEmpty, vmNetwork, rateFormatter);
}

function percentSeries(samples, source, metrics) {
  const rows = collectRows(samples, source, Object.keys(metrics), (sample) => clamp(sample.value, 0, 100));
  return toChartData(rows, metrics);
}

function rateSeries(samples, source, metrics) {
  const previous = {};
  const rows = new Map();
  samples
    .filter(sample => sample.source === source && Object.prototype.hasOwnProperty.call(metrics, sample.metric))
    .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp))
    .forEach(sample => {
      const timestamp = Date.parse(sample.timestamp);
      const last = previous[sample.metric];
      previous[sample.metric] = { timestamp, value: Number(sample.value) };
      if (!last) return;
      const seconds = Math.max(1, (timestamp - last.timestamp) / 1000);
      const delta = Math.max(0, Number(sample.value) - last.value);
      const key = sample.timestamp;
      const row = rows.get(key) || { label: timeLabel(sample.timestamp), values: {} };
      row.values[sample.metric] = delta / seconds;
      rows.set(key, row);
    });
  return toChartData(rows, metrics);
}

function collectRows(samples, source, metricNames, valueMapper) {
  const rows = new Map();
  samples
    .filter(sample => sample.source === source && metricNames.includes(sample.metric))
    .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp))
    .forEach(sample => {
      const key = sample.timestamp;
      const row = rows.get(key) || { label: timeLabel(sample.timestamp), values: {} };
      row.values[sample.metric] = valueMapper(sample);
      rows.set(key, row);
    });
  return rows;
}

function toChartData(rows, metrics) {
  const rowList = Array.from(rows.values());
  const labels = rowList.map(row => row.label);
  const colors = ['#181E9F', '#0a7a26', '#a56600', '#5b21b6'];
  const datasets = Object.entries(metrics).map(([metric, label], idx) => ({
    label,
    data: rowList.map(row => row.values[metric] ?? null),
    borderColor: colors[idx % colors.length],
    backgroundColor: colors[idx % colors.length],
    borderWidth: 2,
    pointRadius: 0,
    tension: 0.25,
    spanGaps: true,
  }));
  const hasData = datasets.some(dataset => dataset.data.some(value => value != null));
  return { labels, datasets, hasData };
}

function renderChart(key, canvas, emptyEl, data, formatter) {
  const empty = !data.hasData;
  showEmpty(canvas, emptyEl, empty);
  if (empty || !canvas) {
    if (charts[key]) {
      charts[key].destroy();
      delete charts[key];
    }
    return;
  }
  const config = {
    type: 'line',
    data: { labels: data.labels, datasets: data.datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 10, usePointStyle: true } },
        tooltip: { callbacks: { label: item => `${item.dataset.label}: ${formatter(item.parsed.y || 0)}` } },
      },
      scales: {
        x: { grid: { display: false }, ticks: { maxTicksLimit: 6 } },
        y: { beginAtZero: true, ticks: { callback: value => formatter(Number(value)) } },
      },
    },
  };
  if (charts[key]) {
    charts[key].data = config.data;
    charts[key].options = config.options;
    charts[key].update();
  } else {
    charts[key] = new Chart(canvas, config);
  }
}

function showEmpty(canvas, emptyEl, empty) {
  const frame = canvas && canvas.closest ? canvas.closest('.chart-frame') : null;
  if (frame) frame.classList.toggle('hidden', empty);
  else if (canvas) canvas.classList.toggle('hidden', empty);
  if (emptyEl) emptyEl.classList.toggle('hidden', !empty);
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, Number(value)));
}

function percentFormatter(value) {
  return `${Number(value).toFixed(0)}%`;
}

function rateFormatter(value) {
  const n = Number(value);
  if (n >= 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB/s`;
  if (n >= 1024) return `${(n / 1024).toFixed(1)} KB/s`;
  return `${n.toFixed(0)} B/s`;
}

function timeLabel(timestamp) {
  return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

async function fetchWebhooks() {
  try {
    const resp = await fetch(`${API}/monitoring/webhooks`, { cache: 'no-store' });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const hooks = await resp.json();
    webhookList.innerHTML = '';
    if (!hooks.length) {
      webhookList.innerHTML = '<div class="small">No webhooks configured.</div>';
      return;
    }
    hooks.forEach(hook => {
      const row = document.createElement('div');
      row.className = 'alert-row';
      row.innerHTML = `<div>${hook.enabled ? 'Enabled' : 'Disabled'}</div><div><strong>${hook.name}</strong><div class="small">${hook.url}</div></div><div class="small">${hook.last_status || 'Never sent'}</div>`;
      webhookList.appendChild(row);
    });
  } catch {
    webhookList.innerHTML = '<div class="small">Failed to load webhooks.</div>';
  }
}

async function fetchSummary() {
  try {
    await fetchMonitoring();
    const resp = await fetch(`${API}/summary`, { cache: 'no-store' });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    statusDiv.textContent = (data.status || 'running').charAt(0).toUpperCase() + (data.status || 'running').slice(1);
    envDiv.textContent = `${(data.env && data.env.environment) || ''} ${(data.env && data.env.network) ? '(' + data.env.network + ')' : ''}`.trim();
    const res = data.resources || {};
    resourcesDiv.textContent = fmtRes(res.available, res.total);
    pricingDiv.textContent = fmtPricing(data.pricing);
    renderVMs(data.vms);
  } catch (e) {
    statusDiv.textContent = 'Stopped';
    statusDiv.classList.remove('ok');
    statusDiv.classList.add('err');
    envDiv.textContent = '';
    resourcesDiv.textContent = '—';
    pricingDiv.textContent = '—';
    vmListDiv.innerHTML = '<div class="vm-row">Provider not running</div>';
  }
}

if (stopBtn && startBtn && statusDiv) {
  document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.section').forEach(p => p.classList.add('hidden'));
      btn.classList.add('active');
      const panel = document.getElementById(btn.dataset.tab);
      if (panel) panel.classList.remove('hidden');
      if (btn.dataset.tab === 'integrationsPanel') fetchWebhooks();
    });
  });

  if (webhookAdd) {
    webhookAdd.addEventListener('click', async () => {
      const name = (webhookName.value || '').trim();
      const url = (webhookUrl.value || '').trim();
      if (!name || !url) return;
      webhookAdd.disabled = true;
      try {
        await fetch(`${API}/monitoring/webhooks`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, url, enabled: true }),
        });
        webhookName.value = '';
        webhookUrl.value = '';
        await fetchWebhooks();
      } finally {
        webhookAdd.disabled = false;
      }
    });
  }

  if (chartRanges) {
    chartRanges.querySelectorAll('.range-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        chartRange = btn.dataset.range || '1h';
        chartRanges.querySelectorAll('.range-btn').forEach(item => item.classList.remove('active'));
        btn.classList.add('active');
        fetchCharts();
      });
    });
  }

  // First-run Multipass check
  if (window.electronAPI && window.electronAPI.checkMultipass) {
    window.electronAPI.checkMultipass().then((res) => {
      if (!res || !res.ok) {
        if (bannerDiv) {
          bannerDiv.style.display = 'block';
          bannerDiv.innerHTML = `
            <strong>Multipass not detected.</strong>
            <span class="muted">Golem Provider requires Canonical Multipass to run VMs.</span>
            <a href="#" id="installMultipass">Install Multipass</a>
          `;
          const a = document.getElementById('installMultipass');
          if (a) {
            a.addEventListener('click', (e) => {
              e.preventDefault();
              const url = 'https://multipass.run/';
              if (window.electronAPI && window.electronAPI.openExternal) window.electronAPI.openExternal(url);
            });
          }
        }
      }
    }).catch(() => {});
  }

  stopBtn.addEventListener('click', async () => {
    actionMsg.textContent = 'Stopping provider...';
    try {
      await fetch(`${API}/admin/shutdown`, { method: 'POST' });
      if (window.electronAPI) window.electronAPI.requestShutdown();
    } catch {}
  });
  startBtn.addEventListener('click', async () => {
    try {
      if (window.electronAPI && window.electronAPI.providerStart) {
        await window.electronAPI.providerStart();
        actionMsg.textContent = 'Provider start requested.';
      } else {
        actionMsg.textContent = 'Provider already running.';
      }
    } catch {
      actionMsg.textContent = 'Failed to start provider.';
    }
  });
  if (window.electronAPI && window.electronAPI.onProviderStatusUpdate) {
    window.electronAPI.onProviderStatusUpdate((s) => {
      if (s && s.message) actionMsg.textContent = s.message;
    });
  }
  // initial and poll
  fetchSummary().then(fetchCharts);
  setInterval(fetchSummary, 3000);
  setInterval(fetchCharts, 30000);
} else {
  document.body.innerHTML = '<h1>Failed to initialize GUI</h1>';
}
