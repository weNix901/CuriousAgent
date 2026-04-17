async function loadExternalView() {
  await Promise.all([
    loadHookBoard(),
    loadAgentActivity(),
    loadTimeline(),
  ]);
}

async function loadHookBoard() {
  var el = document.getElementById('hook-board');
  if (!el) return;
  try {
    var filter = document.getElementById('hook-filter').value;
    var url = '/api/audit/hooks?limit=20' + (filter ? '&hook=' + filter : '');
    var data = await fetchJSON(url);
    if (!data.records || !data.records.length) {
      el.innerHTML = '<div class="empty">暂无 Hook 调用记录</div>';
      return;
    }
    var html = data.records.map(function(r) {
      var emoji = r.status === 'success' ? '✅' : '❌';
      return '<div class="history-item">'
        + '<div class="history-top"><span>' + emoji + ' ' + escapeHtml(r.hook_name) + '</span>'
        + '<span class="history-time">' + r.latency_ms + 'ms</span></div>'
        + '<div class="history-findings">' + escapeHtml(r.endpoint) + ' → ' + r.status_code + '</div></div>';
    }).join('');
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = '<div class="empty">加载失败</div>';
  }
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