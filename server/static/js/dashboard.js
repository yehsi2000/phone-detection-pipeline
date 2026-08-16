// PhoneGuard AI — Central Dashboard Controller

let currentTab = 'monitor-tab';
let currentTriageItem = null;
let currentCanvasBox = null; // [x1, y1, x2, y2] in original image coordinates
let triageImageObj = null;
let isDrawingBox = false;
let drawStart = { x: 0, y: 0 };
let currentTrainingJobId = null;

// Initialize on DOM Load
document.addEventListener('DOMContentLoaded', () => {
    initNavTabs();
    initCanvasEvents();
    refreshAll();

    // Periodic live refresh every 5 seconds
    setInterval(() => {
        if (currentTab === 'monitor-tab') {
            refreshStats();
            refreshDevices();
        }
    }, 5000);
});

// Tab Navigation
function initNavTabs() {
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.getAttribute('data-tab');
            switchTab(tabId);
        });
    });
}

function switchTab(tabId) {
    currentTab = tabId;
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.toggle('active', b.getAttribute('data-tab') === tabId));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.toggle('active', c.id === tabId));

    if (tabId === 'monitor-tab') {
        refreshAll();
    } else if (tabId === 'logs-tab') {
        loadLogsTable();
    } else if (tabId === 'triage-tab') {
        loadTriageQueue();
        loadDatasetStats();
    } else if (tabId === 'model-tab') {
        loadModelVersions();
        loadDatasetStats();
    }
}

function switchToModelLab() {
    switchTab('model-tab');
}

// Global Refresh
function refreshAll() {
    refreshStats();
    refreshDevices();
    refreshLogsFeed();
    loadActiveModelInfo();
}

// Fetch Active Model Info
async function loadActiveModelInfo() {
    try {
        const res = await fetch('/api/model/latest');
        const data = await res.json();
        const pill = document.getElementById('active-model-name');
        if (data.available) {
            pill.textContent = `${data.version} (${data.backbone})`;
        } else {
            pill.textContent = 'None';
        }
    } catch (e) {
        console.error('Failed to load active model info', e);
    }
}

// Fetch Summary Stats
async function refreshStats() {
    try {
        const res = await fetch('/api/telemetry/stats');
        const data = await res.json();
        document.getElementById('stat-total-events').textContent = data.total_events || 0;
        document.getElementById('stat-unreviewed').textContent = data.unreviewed_count || 0;
        document.getElementById('stat-true-pos').textContent = data.true_positives || 0;
        document.getElementById('stat-false-pos').textContent = data.false_positives || 0;
        document.getElementById('stat-online-devices').textContent = `${data.online_devices} / ${data.total_devices}`;
        
        const badge = document.getElementById('pending-badge');
        badge.textContent = data.unreviewed_count || 0;
        badge.style.display = data.unreviewed_count > 0 ? 'inline-block' : 'none';
    } catch (e) {
        console.error('Failed to refresh stats', e);
    }
}

// Fetch Connected Devices
async function refreshDevices() {
    try {
        const res = await fetch('/api/telemetry/devices');
        const devices = await res.json();
        const tbody = document.getElementById('devices-tbody');
        tbody.innerHTML = '';

        if (!devices || devices.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center">연결된 클라이언트가 없습니다.</td></tr>';
            return;
        }

        devices.forEach(d => {
            const tr = document.createElement('tr');
            const statusClass = d.status === 'ONLINE' ? 'text-success' : 'text-muted';
            tr.innerHTML = `
                <td><code>${d.client_id}</code></td>
                <td><strong>${d.hostname || '-'}</strong></td>
                <td>${d.username || '-'}</td>
                <td>${d.os_info || '-'}</td>
                <td><small>${d.last_seen || '-'}</small></td>
                <td><span class="status-pill ${statusClass}">● ${d.status}</span></td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error('Failed to load devices', e);
    }
}

// Recent Logs Feed
async function refreshLogsFeed() {
    try {
        const res = await fetch('/api/telemetry/logs?limit=5');
        const data = await res.json();
        const container = document.getElementById('live-feed-container');
        container.innerHTML = '';

        if (!data.items || data.items.length === 0) {
            container.innerHTML = '<p class="text-muted p-3">최근 이벤트가 없습니다.</p>';
            return;
        }

        data.items.forEach(item => {
            const div = document.createElement('div');
            div.className = 'queue-item';
            const thumbUrl = item.frame_url || item.screen_url || '/static/assets/placeholder.png';
            div.innerHTML = `
                <img src="${thumbUrl}" class="queue-thumb" alt="event">
                <div class="queue-info">
                    <span class="queue-title">${item.event}</span>
                    <span class="queue-sub">${item.timestamp} (${item.device || item.client_id})</span>
                </div>
            `;
            div.onclick = () => openLogModal(item);
            container.appendChild(div);
        });
    } catch (e) {
        console.error('Failed to load logs feed', e);
    }
}

// TAB 2: Load Logs Table
async function loadLogsTable() {
    const eventFilter = document.getElementById('filter-event').value;
    const reviewFilter = document.getElementById('filter-review').value;

    try {
        const url = `/api/telemetry/logs?event=${encodeURIComponent(eventFilter)}&review_status=${encodeURIComponent(reviewFilter)}&limit=100`;
        const res = await fetch(url);
        const data = await res.json();
        const tbody = document.getElementById('logs-tbody');
        tbody.innerHTML = '';

        if (!data.items || data.items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" class="text-center">해당 조건의 로그가 없습니다.</td></tr>';
            return;
        }

        data.items.forEach(l => {
            const tr = document.createElement('tr');
            const confStr = l.confidence && l.confidence.length ? l.confidence.map(c => c.toFixed(2)).join(', ') : '-';
            const frameThumb = l.frame_url ? `<img src="${l.frame_url}" class="thumb-preview" onclick='viewFullImage("${l.frame_url}")'>` : '-';
            const screenThumb = l.screen_url ? `<img src="${l.screen_url}" class="thumb-preview" onclick='viewFullImage("${l.screen_url}")'>` : '-';

            let statusBadge = `<span class="badge badge-indigo">${l.review_status}</span>`;
            if (l.review_status === 'TRUE_POSITIVE') statusBadge = `<span class="badge" style="background:var(--success)">정탐 (TP)</span>`;
            if (l.review_status === 'FALSE_POSITIVE') statusBadge = `<span class="badge" style="background:var(--danger)">오탐 (FP)</span>`;
            if (l.review_status === 'UNREVIEWED') statusBadge = `<span class="badge" style="background:var(--warning); color:#000;">검수 필요</span>`;

            tr.innerHTML = `
                <td>${l.id}</td>
                <td><small>${l.timestamp}</small></td>
                <td><strong>${l.device || l.client_id}</strong><br><small>${l.username}</small></td>
                <td>${l.event}</td>
                <td><code>${confStr}</code></td>
                <td>${frameThumb}</td>
                <td>${screenThumb}</td>
                <td>${statusBadge}</td>
                <td>
                    <button class="btn-sm" onclick='openLogModal(${JSON.stringify(l)})'>상세보기</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error('Failed to load logs table', e);
    }
}

// TAB 3: Triage Studio Queue & Canvas
async function loadTriageQueue() {
    try {
        const res = await fetch('/api/triage/pending');
        const data = await res.json();
        const list = document.getElementById('triage-queue-list');
        const countSpan = document.getElementById('triage-count');
        countSpan.textContent = data.count || 0;
        list.innerHTML = '';

        if (!data.items || data.items.length === 0) {
            list.innerHTML = '<p class="text-muted p-3 text-center">검수할 대기 항목이 없습니다! 🎉</p>';
            currentTriageItem = null;
            clearCanvas();
            return;
        }

        data.items.forEach((item, index) => {
            const div = document.createElement('div');
            div.className = `queue-item ${index === 0 ? 'active' : ''}`;
            div.innerHTML = `
                <img src="${item.frame_url}" class="queue-thumb" alt="frame">
                <div class="queue-info">
                    <span class="queue-title">#${item.id} — ${item.timestamp}</span>
                    <span class="queue-sub">${item.device || item.client_id}</span>
                </div>
            `;
            div.onclick = () => selectTriageItem(item, div);
            list.appendChild(div);
        });

        // Select first item by default
        selectTriageItem(data.items[0], list.children[0]);
    } catch (e) {
        console.error('Failed to load triage queue', e);
    }
}

function selectTriageItem(item, element) {
    currentTriageItem = item;
    document.querySelectorAll('.queue-item').forEach(el => el.classList.remove('active'));
    if (element) element.classList.add('active');

    document.getElementById('current-item-info').textContent = `[ID #${item.id}] ${item.timestamp} | ${item.device || item.client_id} (${item.username})`;
    currentCanvasBox = item.bbox ? [...item.bbox] : null;

    loadCanvasImage(item.frame_url);
}

// Canvas Drawing & Bounding Box Visualizer
function initCanvasEvents() {
    const canvas = document.getElementById('triage-canvas');
    if (!canvas) return;

    canvas.addEventListener('mousedown', (e) => {
        if (!triageImageObj) return;
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;

        drawStart.x = (e.clientX - rect.left) * scaleX;
        drawStart.y = (e.clientY - rect.top) * scaleY;
        isDrawingBox = true;
    });

    canvas.addEventListener('mousemove', (e) => {
        if (!isDrawingBox || !triageImageObj) return;
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;

        const currentX = (e.clientX - rect.left) * scaleX;
        const currentY = (e.clientY - rect.top) * scaleY;

        const x1 = Math.min(drawStart.x, currentX);
        const y1 = Math.min(drawStart.y, currentY);
        const x2 = Math.max(drawStart.x, currentX);
        const y2 = Math.max(drawStart.y, currentY);

        currentCanvasBox = [Math.round(x1), Math.round(y1), Math.round(x2), Math.round(y2)];
        drawCanvas();
    });

    canvas.addEventListener('mouseup', () => {
        isDrawingBox = false;
    });
}

function loadCanvasImage(url) {
    const placeholder = document.getElementById('canvas-placeholder');
    placeholder.style.display = 'none';

    const canvas = document.getElementById('triage-canvas');
    const ctx = canvas.getContext('2d');

    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.src = url;
    img.onload = () => {
        triageImageObj = img;
        canvas.width = img.naturalWidth || 640;
        canvas.height = img.naturalHeight || 480;
        drawCanvas();
    };
}

function drawCanvas() {
    const canvas = document.getElementById('triage-canvas');
    const ctx = canvas.getContext('2d');
    if (!triageImageObj) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(triageImageObj, 0, 0, canvas.width, canvas.height);

    if (currentCanvasBox && currentCanvasBox.length === 4) {
        const [x1, y1, x2, y2] = currentCanvasBox;
        const w = x2 - x1;
        const h = y2 - y1;

        // Draw neon bounding box
        ctx.strokeStyle = '#34d399';
        ctx.lineWidth = 3;
        ctx.strokeRect(x1, y1, w, h);

        // Draw Label Tag
        ctx.fillStyle = '#34d399';
        ctx.fillRect(x1, Math.max(0, y1 - 24), Math.max(80, ctx.measureText('Phone').width + 20), 24);
        ctx.fillStyle = '#04101d';
        ctx.font = 'bold 14px Inter, sans-serif';
        ctx.fillText('Phone', x1 + 6, Math.max(16, y1 - 6));
    }
}

function resetCanvasBox() {
    currentCanvasBox = null;
    drawCanvas();
}

function clearCanvas() {
    const canvas = document.getElementById('triage-canvas');
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    triageImageObj = null;
    currentCanvasBox = null;
    document.getElementById('canvas-placeholder').style.display = 'block';
    document.getElementById('current-item-info').textContent = '선택된 항목 없음';
}

// Classify Current Triage Item
async function classifyCurrent(status) {
    if (!currentTriageItem) {
        alert('검수할 항목이 선택되지 않았습니다.');
        return;
    }

    try {
        const payload = {
            log_id: currentTriageItem.id,
            status: status,
            bbox: (status === 'TRUE_POSITIVE') ? currentCanvasBox : null
        };

        const res = await fetch('/api/triage/classify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            refreshStats();
            loadDatasetStats();
            loadTriageQueue(); // Moves to next item automatically
        } else {
            alert('검수 상태 업데이트 실패');
        }
    } catch (e) {
        console.error('Classification error', e);
    }
}

// Load Dataset Accumulation Stats
async function loadDatasetStats() {
    try {
        const res = await fetch('/api/triage/dataset_stats');
        const data = await res.json();
        document.getElementById('dataset-pos-count').textContent = data.positive_samples || 0;
        document.getElementById('dataset-neg-count').textContent = data.hard_negative_samples || 0;
        document.getElementById('dataset-total-count').textContent = data.total_dataset_items || 0;
    } catch (e) {
        console.error('Failed to load dataset stats', e);
    }
}

// TAB 4: Model Lab & Fine-Tuning
async function startTraining() {
    const backbone = document.getElementById('backbone-select').value;
    const epochs = parseInt(document.getElementById('epochs-input').value) || 30;
    const batchSize = parseInt(document.getElementById('batch-input').value) || 16;
    const device = document.getElementById('device-select').value;

    const btn = document.getElementById('btn-start-train');
    const msg = document.getElementById('train-status-msg');
    const monitorBox = document.getElementById('train-monitor-box');
    const terminal = document.getElementById('terminal-output');

    btn.disabled = true;
    msg.textContent = '🚀 학습 작업을 초기화하고 있습니다...';
    monitorBox.style.display = 'block';
    terminal.innerHTML = '<div class="terminal-line">[SYSTEM] Starting fine-tuning job...</div>';

    try {
        const res = await fetch('/api/training/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ backbone, epochs, batch_size: batchSize, device })
        });

        const data = await res.json();
        if (res.ok && data.job_id) {
            currentTrainingJobId = data.job_id;
            msg.textContent = `학습 진행 중: ${data.job_id} (${data.backbone})`;
            streamLogs(data.job_id);
            pollTrainingStatus(data.job_id, epochs);
        } else {
            msg.textContent = `오류: ${data.detail || '학습 시작 실패'}`;
            btn.disabled = false;
        }
    } catch (e) {
        msg.textContent = `통신 에러: ${e}`;
        btn.disabled = false;
    }
}

function streamLogs(jobId) {
    const terminal = document.getElementById('terminal-output');
    const eventSource = new EventSource(`/api/training/stream/${jobId}`);

    eventSource.onmessage = (e) => {
        const line = document.createElement('div');
        line.className = 'terminal-line';
        line.textContent = e.data;
        terminal.appendChild(line);
        terminal.scrollTop = terminal.scrollHeight;

        if (e.data.includes('[STATUS] COMPLETED') || e.data.includes('[STATUS] FAILED')) {
            eventSource.close();
            document.getElementById('btn-start-train').disabled = false;
            loadModelVersions();
            loadActiveModelInfo();
        }
    };

    eventSource.onerror = () => {
        eventSource.close();
    };
}

function pollTrainingStatus(jobId, totalEpochs) {
    const interval = setInterval(async () => {
        try {
            const res = await fetch(`/api/training/status/${jobId}`);
            const data = await res.json();

            const prog = data.progress || 0;
            document.getElementById('train-progress-fill').style.width = `${prog}%`;
            document.getElementById('train-percent-label').textContent = `${prog}%`;
            document.getElementById('train-epoch-label').textContent = `Epoch: ${data.current_epoch || 0} / ${data.total_epochs || totalEpochs}`;

            if (data.status === 'COMPLETED') {
                clearInterval(interval);
                document.getElementById('train-status-msg').textContent = '✅ 파인튜닝 및 ONNX 변환 완료!';
                document.getElementById('btn-start-train').disabled = false;
                loadModelVersions();
            } else if (data.status === 'FAILED') {
                clearInterval(interval);
                document.getElementById('train-status-msg').textContent = '❌ 학습 실패 (로그 확인)';
                document.getElementById('btn-start-train').disabled = false;
            }
        } catch (e) {
            console.error('Polling error', e);
        }
    }, 1500);
}

// Load Model Versions for Benchmark Comparison
async function loadModelVersions() {
    try {
        const res = await fetch('/api/model/versions');
        const versions = await res.json();
        const tbody = document.getElementById('models-tbody');
        tbody.innerHTML = '';

        if (!versions || versions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10" class="text-center">등록된 모델이 없습니다.</td></tr>';
            return;
        }

        versions.forEach(v => {
            const tr = document.createElement('tr');
            const activeBadge = v.is_active
                ? '<span class="badge" style="background:var(--success);">ACTIVE (배포중)</span>'
                : '<span class="badge badge-indigo">보관됨</span>';

            const deployBtn = v.is_active
                ? '<button class="btn btn-sm btn-outline" disabled>현재 배포중</button>'
                : `<button class="btn btn-sm btn-primary" onclick='deployModelVersion("${v.version_tag}")'>🚀 이 모델 배포하기</button>`;

            tr.innerHTML = `
                <td><code><strong>${v.version_tag}</strong></code></td>
                <td><span class="badge badge-indigo">${v.backbone}</span></td>
                <td><strong>${(v.map50 * 100).toFixed(1)}%</strong></td>
                <td>${(v.precision * 100).toFixed(1)}%</td>
                <td>${(v.recall * 100).toFixed(1)}%</td>
                <td><strong>${(v.f1_score * 100).toFixed(1)}%</strong></td>
                <td><code>${v.latency_ms.toFixed(1)} ms</code></td>
                <td>${v.file_size_mb.toFixed(1)} MB</td>
                <td>${activeBadge}</td>
                <td>${deployBtn}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error('Failed to load model versions', e);
    }
}

// Deploy Model Version
async function deployModelVersion(versionTag) {
    if (!confirm(`모델 버전 [${versionTag}]을 모든 클라이언트에 즉시 배포하시겠습니까?`)) return;

    try {
        const res = await fetch(`/api/model/deploy/${encodeURIComponent(versionTag)}`, { method: 'POST' });
        if (res.ok) {
            alert(`✅ 모델 [${versionTag}]이 성공적으로 활성화되었습니다! 클라이언트가 자동으로 새 모델을 다운로드합니다.`);
            loadModelVersions();
            loadActiveModelInfo();
        } else {
            alert('모델 배포 실패');
        }
    } catch (e) {
        console.error('Deploy error', e);
    }
}

// Modal Helpers
function viewFullImage(url) {
    const modal = document.getElementById('log-modal');
    const body = document.getElementById('modal-body');
    body.innerHTML = `<img src="${url}" style="width:100%; border-radius:8px;" alt="full">`;
    modal.classList.add('active');
}

function openLogModal(log) {
    const modal = document.getElementById('log-modal');
    const body = document.getElementById('modal-body');
    const appsList = log.active_apps ? log.active_apps.map(a => `<li>${a.process || a}: ${a.title || ''}</li>`).join('') : 'None';

    body.innerHTML = `
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:14px;">
            <div>
                <h5>카메라 프레임</h5>
                ${log.frame_url ? `<img src="${log.frame_url}" style="width:100%; border-radius:6px;">` : 'None'}
            </div>
            <div>
                <h5>스크린샷</h5>
                ${log.screen_url ? `<img src="${log.screen_url}" style="width:100%; border-radius:6px;">` : 'None'}
            </div>
        </div>
        <div style="font-size:13px; line-height:1.6;">
            <p><strong>일시:</strong> ${log.timestamp}</p>
            <p><strong>기기/사용자:</strong> ${log.device || log.client_id} (${log.username})</p>
            <p><strong>이벤트:</strong> ${log.event}</p>
            <p><strong>실행 중이던 앱:</strong></p>
            <ul style="padding-left:20px;">${appsList}</ul>
        </div>
    `;
    modal.classList.add('active');
}

function closeModal() {
    document.getElementById('log-modal').classList.remove('active');
}
