async function loadInternalView() {
  await Promise.all([
    loadExplorerPanel(),
    loadDreamPanel(),
    loadQueueViz(),
    loadKgStats(),
    loadSystemHealth(),
  ]);
}

async function loadExplorerPanel() {
  var el = document.getElementById('explorer-panel');
  if (!el) return;
  try {
    var data = await fetchJSON('/api/explorer/recent?limit=10');
    if (!data.traces || !data.traces.length) {
      el.innerHTML = '<div class="empty">暂无探索记录</div>';
      return;
    }
    var html = data.traces.map(function(t) {
      var emoji = t.status === 'done' ? '✅' : (t.status === 'failed' ? '❌' : '🔄');
      var label = t.status === 'done' ? '完成' : (t.status === 'failed' ? '失败' : '进行中');
      return '<div class="history-item" onclick="showExplorerTrace(\'' + t.trace_id + '\')">'
        + '<div class="history-top"><span>' + emoji + ' [' + label + '] ' + escapeHtml(t.topic) + '</span>'
        + '<span class="history-time">' + t.total_steps + ' steps | ' + (t.duration_ms || 0) + 'ms</span></div>'
        + '</div>';
    }).join('');
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = '<div class="empty">加载失败</div>';
  }
}

async function loadDreamPanel() {
  var el = document.getElementById('dream-panel');
  if (!el) return;
  try {
    var stats = await fetchJSON('/api/dream/stats');
    var html = '<div class="stat-card"><div class="stat-label">总梦境</div><div class="stat-value">' + stats.total_dreams + '</div></div>'
      + '<div class="stat-card"><div class="stat-label">洞察数</div><div class="stat-value">' + stats.total_insights + '</div></div>';
    el.innerHTML = '<div class="stats">' + html + '</div>';
  } catch (e) {
    el.innerHTML = '<div class="empty">加载失败</div>';
  }
}

async function loadQueueViz() {
  var el = document.getElementById('queue-viz-panel');
  if (!el) return;
  try {
    var stats = await fetchJSON('/api/queue');
    var s = stats.stats || {};
    var html = '<div class="stat-card"><div class="stat-label">Pending</div><div class="stat-value">' + (s.pending || 0) + '</div></div>'
      + '<div class="stat-card"><div class="stat-label">Completed</div><div class="stat-value">' + (s.completed || 0) + '</div></div>';
    el.innerHTML = '<div class="stats">' + html + '</div>';
  } catch (e) {
    el.innerHTML = '<div class="empty">加载失败</div>';
  }
}

async function loadKgStats() {
  var el = document.getElementById('kg-stats-panel');
  if (!el) return;
  try {
    var stats = await fetchJSON('/api/kg/stats');
    var html = '<div class="stat-card"><div class="stat-label">节点</div><div class="stat-value">' + stats.total_nodes + '</div></div>'
      + '<div class="stat-card"><div class="stat-label">边</div><div class="stat-value">' + stats.total_edges + '</div></div>';
    el.innerHTML = '<div class="stats">' + html + '</div>';
  } catch (e) {
    el.innerHTML = '<div class="empty">加载失败</div>';
  }
}

async function loadSystemHealth() {
  var el = document.getElementById('health-panel');
  if (!el) return;
  try {
    var health = await fetchJSON('/api/system/health');
    var sys = health.system || {};
    var html = '<div class="stat-card"><div class="stat-label">CPU</div><div class="stat-value">' + sys.cpu_percent + '%</div></div>'
      + '<div class="stat-card"><div class="stat-label">Memory</div><div class="stat-value">' + sys.memory_percent + '%</div></div>';
    el.innerHTML = '<div class="stats">' + html + '</div>';
  } catch (e) {
    el.innerHTML = '<div class="empty">加载失败</div>';
  }
}

function refreshExplorer() { loadExplorerPanel(); }
function refreshDream() { loadDreamPanel(); }

async function showExplorerTrace(traceId) {
  var modal = document.getElementById('detail-modal');
  var title = document.getElementById('modal-title');
  var meta = document.getElementById('modal-meta');
  var body = document.getElementById('modal-body');
  
  title.textContent = 'Explorer Trace';
  meta.innerHTML = '<span class="modal-meta-item">' + traceId + '</span>';
  body.innerHTML = '<div class="empty">加载中...</div>';
  modal.classList.add('active');
  
  try {
    var data = await fetchJSON('/api/explorer/trace/' + traceId);
    var steps = data.steps || [];
    var html = steps.map(function(s) {
      return '<div class="history-item"><div class="history-top">'
        + '<span>Step ' + s.step_num + ': ' + escapeHtml(s.action) + '</span>'
        + '<span class="history-time">' + s.duration_ms + 'ms</span></div>'
        + '<div class="history-findings">' + escapeHtml(s.output_summary || '').slice(0, 100) + '</div></div>';
    }).join('');
    body.innerHTML = html || '<div class="empty">无步骤记录</div>';
  } catch (e) {
    body.innerHTML = '<div class="empty">加载失败</div>';
  }
}