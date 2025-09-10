const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const statusDiv = document.getElementById('status');
const envDiv = document.getElementById('env');
const resourcesDiv = document.getElementById('resources');
const pricingDiv = document.getElementById('pricing');
const vmListDiv = document.getElementById('vmList');
const actionMsg = document.getElementById('actionMsg');
const bannerDiv = document.getElementById('banner');

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

function renderVMs(vms) {
  vmListDiv.innerHTML = '';
  const list = Array.isArray(vms) ? vms : [];
  if (list.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'vm-row';
    empty.textContent = 'No VMs running';
    vmListDiv.appendChild(empty);
    return;
  }
  list.forEach((vm, idx) => {
    const row = document.createElement('div');
    row.className = 'vm-row';
    const radio = document.createElement('input');
    radio.type = 'radio';
    radio.name = 'vmSelect';
    radio.value = vm.id;
    if (idx === 0) radio.checked = true;
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
    row.appendChild(radio);
    row.appendChild(id);
    row.appendChild(status);
    row.appendChild(res);
    vmListDiv.appendChild(row);
  });
}

async function fetchSummary() {
  try {
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
  fetchSummary();
  setInterval(fetchSummary, 3000);
} else {
  document.body.innerHTML = '<h1>Failed to initialize GUI</h1>';
}
