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
        + '<span class="click-hint">👆 详情</span></div>';
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
    var data = await fetchJSON('/api/dream/traces?limit=10');
    if (!data.traces || !data.traces.length) {
      el.innerHTML = '<div class="empty">暂无Dream洞察记录</div>';
      return;
    }
    var html = data.traces.map(function(t) {
      var emoji = t.status === 'done' ? '✅' : (t.status === 'failed' ? '❌' : '🔄');
      var label = t.status === 'done' ? '完成' : (t.status === 'failed' ? '失败' : '进行中');
      var insightsCount = t.l4_count || 0;
      var started = t.started_at ? timeAgo(t.started_at) : '';
      return '<div class="history-item" onclick="showDreamTrace(\'' + t.trace_id + '\')">'
        + '<div class="history-top"><span>' + emoji + ' [' + label + '] Dream #' + t.trace_id.slice(0, 8) + '</span>'
        + '<span class="history-time">' + insightsCount + ' insights | ' + (t.total_duration_ms || 0) + 'ms</span></div>'
        + '<div class="history-findings">L1: ' + (t.l1_count || 0) + ' → L2: ' + (t.l2_count || 0) + ' → L3: ' + (t.l3_count || 0) + ' → L4: ' + insightsCount + '</div>'
        + '<span class="click-hint">👆 详情</span></div>';
    }).join('');
    el.innerHTML = html;
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
  
  title.textContent = '🧭 Explorer Trace';
  meta.innerHTML = '<span class="modal-meta-item">' + traceId.slice(0, 8) + '</span>';
  body.innerHTML = '<div class="empty">加载中...</div>';
  modal.classList.add('active');
  
  try {
    var data = await fetchJSON('/api/explorer/trace/' + traceId);
    var steps = data.steps || [];
    meta.innerHTML = '<span class="modal-meta-item">Topic: ' + escapeHtml(data.topic || '') + '</span>'
      + '<span class="modal-meta-item">' + steps.length + ' steps</span>'
      + '<span class="modal-meta-item">' + (data.duration_ms || 0) + 'ms</span>';
    var html = steps.map(function(s) {
      return '<div class="history-item"><div class="history-top">'
        + '<span>Step ' + s.step_num + ': ' + escapeHtml(s.action) + '</span>'
        + '<span class="history-time">' + s.duration_ms + 'ms</span></div>'
        + '<div class="history-findings">' + escapeHtml(s.output_summary || '').slice(0, 150) + '</div></div>';
    }).join('');
    body.innerHTML = html || '<div class="empty">无步骤记录</div>';
  } catch (e) {
    body.innerHTML = '<div class="empty">加载失败</div>';
  }
}

async function showDreamTrace(traceId) {
  var modal = document.getElementById('detail-modal');
  var title = document.getElementById('modal-title');
  var meta = document.getElementById('modal-meta');
  var body = document.getElementById('modal-body');
  
  title.textContent = '💭 Dream Trace';
  meta.innerHTML = '<span class="modal-meta-item">' + traceId.slice(0, 8) + '</span>';
  body.innerHTML = '<div class="empty">加载中...</div>';
  modal.classList.add('active');
  
  try {
    var data = await fetchJSON('/api/dream/trace/' + traceId);
    var duration = data.total_duration_ms || 0;
    var status = data.status || 'unknown';
    
    meta.innerHTML = '<span class="modal-meta-item">状态: ' + status + '</span>'
      + '<span class="modal-meta-item">' + duration + 'ms</span>';
    
    var html = '<div class="modal-section"><div class="modal-section-title">L1 候选召回</div>'
      + '<div class="modal-section-content">数量: ' + (data.l1_count || 0) + ' | 耗时: ' + (data.l1_duration_ms || 0) + 'ms</div></div>'
      + '<div class="modal-section"><div class="modal-section-title">L2 评分排序</div>'
      + '<div class="modal-section-content">数量: ' + (data.l2_count || 0) + ' | 耗时: ' + (data.l2_duration_ms || 0) + 'ms</div></div>'
      + '<div class="modal-section"><div class="modal-section-title">L3 过滤筛选</div>'
      + '<div class="modal-section-content">数量: ' + (data.l3_count || 0) + ' | 耗时: ' + (data.l3_duration_ms || 0) + 'ms</div></div>'
      + '<div class="modal-section"><div class="modal-section-title">L4 生成话题</div>'
      + '<div class="modal-section-content">数量: ' + (data.l4_count || 0) + ' | 耗时: ' + (data.l4_duration_ms || 0) + 'ms</div></div>';
    
    if (data.l4_topics) {
      try {
        var topics = JSON.parse(data.l4_topics);
        if (topics && topics.length > 0) {
          html += '<div class="modal-section"><div class="modal-section-title">生成的话题</div>'
            + '<div class="modal-section-content"><ul style="margin:0;padding-left:16px;">'
            + topics.map(function(t) {
              return '<li>' + escapeHtml(t.topic || t) + '</li>';
            }).join('')
            + '</ul></div></div>';
        }
      } catch (e) {}
    }
    
    if (data.insights_generated) {
      try {
        var insights = JSON.parse(data.insights_generated);
        if (insights && insights.length > 0) {
          html += '<div class="modal-section"><div class="modal-section-title">洞察内容</div>'
            + '<div class="modal-section-content" style="max-height:150px;overflow-y:auto;">'
            + insights.map(function(i) {
              return escapeHtml(i).slice(0, 100);
            }).join('<br><br>')
            + '</div></div>';
        }
      } catch (e) {}
    }
    
    if (data.error) {
      html += '<div class="modal-section"><div class="modal-section-title">错误</div>'
        + '<div class="modal-section-content" style="color:#f85149;">' + escapeHtml(data.error) + '</div></div>';
    }
    
    body.innerHTML = html;
  } catch (e) {
    body.innerHTML = '<div class="empty">加载失败: ' + e + '</div>';
  }
}