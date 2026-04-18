async function loadExternalView() {
  await loadHookFilter();
  await Promise.all([
    loadHookBoard(),
    loadAgentActivity(),
    loadTimeline(),
  ]);
}

async function loadHookFilter() {
  var select = document.getElementById('hook-filter');
  if (!select) return;
  try {
    var stats = await fetchJSON('/api/audit/hooks/stats');
    var hooks = Object.keys(stats.by_hook || {});
    hooks.sort();
    var html = '<option value="">全部 Hook</option>';
    hooks.forEach(function(h) {
      var info = stats.by_hook[h];
      html += '<option value="' + escapeHtml(h) + '">' + escapeHtml(h) + ' (' + info.total + '次)</option>';
    });
    select.innerHTML = html;
  } catch (e) {
    select.innerHTML = '<option value="">全部 Hook</option>';
  }
}

async function loadHookBoard() {
  var el = document.getElementById('hook-board');
  if (!el) return;
  try {
    var filter = document.getElementById('hook-filter').value;
    var url = '/api/audit/hooks?limit=20' + (filter ? '&hook=' + encodeURIComponent(filter) : '');
    var data = await fetchJSON(url);
    if (!data.records || !data.records.length) {
      el.innerHTML = '<div class="empty">暂无 Hook 调用记录</div>';
      return;
    }
    var html = data.records.map(function(r) {
      var emoji = r.status === 'success' ? '✅' : '❌';
      var hookDisplay = r.hook_name !== 'unknown' ? r.hook_name : r.endpoint;
      return '<div class="history-item" data-hook-id="' + escapeHtml(r.id) + '" onclick="showHookDetail(this.dataset.hookId)">'
        + '<div class="history-top"><span>' + emoji + ' ' + escapeHtml(hookDisplay) + '</span>'
        + '<span class="history-time">' + r.latency_ms + 'ms</span></div>'
        + '<div class="history-findings">' + escapeHtml(r.endpoint) + ' → ' + r.status_code + '</div>'
        + '<span class="click-hint">👆 详情</span></div>';
    }).join('');
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = '<div class="empty">加载失败</div>';
  }
}

async function showHookDetail(hookId) {
  try {
    var data = await fetchJSON('/api/audit/hooks/' + hookId);
    var modal = document.getElementById('detail-modal');
    var title = document.getElementById('modal-title');
    var meta = document.getElementById('modal-meta');
    var body = document.getElementById('modal-body');
    
    var hookDisplay = data.hook_name !== 'unknown' ? data.hook_name : data.endpoint;
    var summary = data.request_raw_topic || '无topic';
    
    title.textContent = '🪝 ' + hookDisplay;
    meta.innerHTML = '<span class="modal-meta-item">时间: ' + timeAgo(data.timestamp) + '</span>'
      + '<span class="modal-meta-item">耗时: ' + data.latency_ms + 'ms</span>'
      + '<span class="modal-meta-item">状态: ' + data.status + '</span>';
    body.innerHTML = '<div class="modal-section"><div class="modal-section-title">基本信息</div>'
      + '<div class="modal-section-content">'
      + 'Endpoint: ' + escapeHtml(data.endpoint) + '<br>'
      + 'Method: ' + data.method + '<br>'
      + 'Agent: ' + data.agent_id + '<br>'
      + 'Status Code: ' + data.status_code + '</div></div>'
      + '<div class="modal-section"><div class="modal-section-title">Topic</div>'
      + '<div class="modal-section-content">' + escapeHtml(summary) + '</div></div>'
      + '<div class="modal-section"><div class="modal-section-title">响应</div>'
      + '<div class="modal-section-content" style="max-height:200px;overflow-y:auto;font-size:12px;white-space:pre-wrap;">'
      + escapeHtml(data.response_payload || '无响应') + '</div></div>';
    
    modal.classList.add('active');
  } catch (e) {
    alert('加载详情失败: ' + e);
  }
}

function closeModal() {
  document.getElementById('detail-modal').classList.remove('active');
}

async function loadAgentActivity() {
  var el = document.getElementById('agent-activity');
  if (!el) return;
  try {
    var data = await fetchJSON('/api/agents');
    if (!data.agents || !data.agents.length) {
      el.innerHTML = '<div class="empty">暂无已接入 Agent</div>';
      return;
    }
    var html = data.agents.map(function(a) {
      return '<div class="panel"><div class="panel-header"><span class="panel-title">' + escapeHtml(a.agent_name) + '</span></div>'
        + '<div class="panel-body"><div class="stats">'
        + '<div class="stat-card"><div class="stat-label">调用数</div><div class="stat-value">' + a.total_calls + '</div></div>'
        + '<div class="stat-card"><div class="stat-label">成功率</div><div class="stat-value">' + (a.success_rate * 100).toFixed(0) + '%</div></div>'
        + '</div></div></div>';
    }).join('');
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = '<div class="empty">加载失败</div>';
  }
}

async function loadTimeline() {
  var el = document.getElementById('timeline-panel');
  if (!el) return;
  try {
    var data = await fetchJSON('/api/timeline?limit=30');
    if (!data.events || !data.events.length) {
      el.innerHTML = '<div class="empty">暂无事件</div>';
      return;
    }
    var html = data.events.map(function(e) {
      return '<div class="history-item">'
        + '<div class="history-top"><span>' + e.emoji + ' ' + escapeHtml(e.summary) + '</span>'
        + '<span class="history-time">' + timeAgo(e.timestamp) + '</span></div></div>';
    }).join('');
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = '<div class="empty">加载失败</div>';
  }
}

function refreshHookBoard() { loadHookBoard(); }
function refreshTimeline() { loadTimeline(); }