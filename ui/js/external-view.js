var bootstrapConfig = {
  enabled: true,
  target_agent: 'researcher',
  timeout_ms: 1500,
  max_nodes: 5,
  min_quality: 0,
  sort_by: 'created_at'
};

async function loadExternalView() {
  await Promise.all([
    loadBootstrapConfig(),
    loadHookBoard(),
    loadAgentActivity(),
    loadTimeline(),
  ]);
}

async function loadBootstrapConfig() {
  try {
    var data = await fetchJSON('/api/hooks/bootstrap/config');
    if (data.config) {
      bootstrapConfig = data.config;
      applyBootstrapConfigToUI();
    }
  } catch (e) {
    applyBootstrapConfigToUI();
  }
}

function applyBootstrapConfigToUI() {
  document.getElementById('bootstrap-enabled').checked = bootstrapConfig.enabled;
  document.getElementById('bootstrap-timeout').value = bootstrapConfig.timeout_ms;
  document.getElementById('bootstrap-timeout-value').textContent = bootstrapConfig.timeout_ms;
  document.getElementById('bootstrap-max-nodes').value = bootstrapConfig.max_nodes;
  document.getElementById('bootstrap-max-nodes-value').textContent = bootstrapConfig.max_nodes;
  document.getElementById('bootstrap-min-quality').value = bootstrapConfig.min_quality;
  document.getElementById('bootstrap-min-quality-value').textContent = bootstrapConfig.min_quality;
  document.getElementById('bootstrap-sort-by').value = bootstrapConfig.sort_by;
  document.getElementById('bootstrap-target-agent').value = bootstrapConfig.target_agent;
}

function updateSliderValue(input) {
  var valueEl = document.getElementById(input.id + '-value');
  if (valueEl) {
    valueEl.textContent = input.value;
  }
}

async function saveBootstrapConfig() {
  var newConfig = {
    enabled: document.getElementById('bootstrap-enabled').checked,
    timeout_ms: parseInt(document.getElementById('bootstrap-timeout').value),
    max_nodes: parseInt(document.getElementById('bootstrap-max-nodes').value),
    min_quality: parseFloat(document.getElementById('bootstrap-min-quality').value),
    sort_by: document.getElementById('bootstrap-sort-by').value,
    target_agent: document.getElementById('bootstrap-target-agent').value
  };
  
  try {
    var response = await fetch('/api/hooks/bootstrap/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newConfig)
    });
    var data = await response.json();
    if (data.status === 'ok') {
      bootstrapConfig = newConfig;
      showToast('✅ 配置已保存（实时生效 + 已持久化）', 'success');
    } else {
      showToast('⚠️ 保存失败: ' + data.error, 'error');
    }
  } catch (e) {
    showToast('⚠️ 保存失败: ' + e.message, 'error');
  }
}

function resetBootstrapConfig() {
  bootstrapConfig = {
    enabled: true,
    target_agent: 'researcher',
    timeout_ms: 1500,
    max_nodes: 5,
    min_quality: 0,
    sort_by: 'created_at'
  };
  applyBootstrapConfigToUI();
  showToast('🔄 已重置为默认值（未保存）', 'info');
}

async function loadHookBoard() {
  var el = document.getElementById('hook-board');
  if (!el) return;
  try {
    var filter = document.getElementById('hook-filter').value;
    var url = '/api/audit/hooks?limit=20' + (filter ? '&hook=' + encodeURIComponent(filter) : '');
    var data = await fetchJSON(url);
    if (!data.records || !data.records.length) {
      el.innerHTML = '<div class="empty"><div class="empty-icon">📭</div>暂无外部Agent调用记录</div>';
      return;
    }
    
    var html = data.records.map(function(r) {
      var emoji = r.status === 'success' ? '✅' : '❌';
      var hookName = r.hook_name;
      var isSkill = hookName && hookName.endsWith('-skill');
      var typeEmoji = isSkill ? '🔹' : '🪝';
      if (hookName === 'unknown' || !hookName) {
        hookName = r.endpoint.split('/').pop();
      }
      var time = r.timestamp ? timeAgo(r.timestamp) : '';
      var injectedBadge = r.knowledge_injected > 0 ? '<span class="badge badge-success">注入' + r.knowledge_injected + '节点</span>' : '';
      return '<div class="history-item" data-hook-id="' + escapeHtml(r.id) + '" onclick="showHookDetail(this.dataset.hookId)">'
        + '<div class="history-top"><span>' + emoji + ' ' + typeEmoji + ' ' + escapeHtml(hookName) + '</span>'
        + '<span class="history-time">' + time + ' | ' + r.latency_ms + 'ms</span></div>'
        + '<div class="history-findings">' + escapeHtml(r.endpoint) + ' → ' + r.status_code + ' ' + injectedBadge + '</div>'
        + '<span class="click-hint">👆 详情</span></div>';
    }).join('');
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = '<div class="empty"><div class="empty-icon">⚠️</div>加载失败</div>';
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
    
    title.textContent = '🤖 ' + hookDisplay;
    
    var metaHtml = '<span class="modal-meta-item">时间: ' + timeAgo(data.timestamp) + '</span>'
      + '<span class="modal-meta-item">耗时: ' + data.latency_ms + 'ms</span>'
      + '<span class="modal-meta-item">状态: ' + data.status + '</span>';
    if (data.knowledge_injected > 0) {
      metaHtml += '<span class="modal-meta-item badge badge-success">注入 ' + data.knowledge_injected + ' 节点</span>';
    }
    meta.innerHTML = metaHtml;
    
    var bodyHtml = '<div class="modal-section"><div class="modal-section-title">基本信息</div>'
      + '<div class="modal-section-content">'
      + 'Endpoint: ' + escapeHtml(data.endpoint) + '<br>'
      + 'Method: ' + data.method + '<br>'
      + 'Agent: ' + data.agent_id + '<br>'
      + 'Status Code: ' + data.status_code + '</div></div>';
    
    if (data.hook_name === 'knowledge-bootstrap-hook' && data.response_payload) {
      try {
        var resp = JSON.parse(data.response_payload);
        var nodes = resp.nodes || [];
        var edges = resp.edges || [];
        bodyHtml += '<div class="modal-section"><div class="modal-section-title">注入内容概览</div>'
          + '<div class="modal-section-content">'
          + '<strong>知识节点:</strong> ' + nodes.length + ' 个<br>'
          + '<strong>知识关系:</strong> ' + edges.length + ' 条<br>'
          + '</div></div>';
        if (nodes.length > 0) {
          var topNodes = nodes.slice(0, 5).map(function(n, i) {
            var qualityBadge = n.quality ? '<span class="badge">' + n.quality.toFixed(1) + '</span>' : '';
            var statusBadge = n.status ? '<span class="badge badge-' + (n.status === 'done' ? 'success' : 'warning') + '">' + n.status + '</span>' : '';
            return '<div class="injected-node">'
              + '<span class="node-index">' + (i + 1) + '</span>'
              + '<span class="node-topic">' + escapeHtml(n.topic || n.id || '未知') + '</span>'
              + qualityBadge + statusBadge
              + '</div>';
          }).join('');
          bodyHtml += '<div class="modal-section"><div class="modal-section-title">Top 5 注入节点</div>'
            + '<div class="modal-section-content injected-nodes-list">' + topNodes + '</div></div>';
        }
      } catch (parseErr) {
        bodyHtml += '<div class="modal-section"><div class="modal-section-title">响应</div>'
          + '<div class="modal-section-content" style="max-height:200px;overflow-y:auto;font-family:var(--font-data);font-size:12px;">'
          + escapeHtml(data.response_payload || '无响应') + '</div></div>';
      }
    } else {
      bodyHtml += '<div class="modal-section"><div class="modal-section-title">响应</div>'
        + '<div class="modal-section-content" style="max-height:200px;overflow-y:auto;font-family:var(--font-data);font-size:12px;">'
        + escapeHtml(data.response_payload || '无响应') + '</div></div>';
    }
    
    if (data.injection_snippet) {
      bodyHtml += '<div class="modal-section"><div class="modal-section-title">注入摘要</div>'
        + '<div class="modal-section-content">' + escapeHtml(data.injection_snippet) + '</div></div>';
    }
    
    body.innerHTML = bodyHtml;
    modal.classList.add('active');
  } catch (e) {
    showToast('加载详情失败: ' + e, 'error');
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
      el.innerHTML = '<div class="empty"><div class="empty-icon">🤖</div>暂无已接入 Agent</div>';
      return;
    }
    var html = data.agents.map(function(a) {
      return '<div class="activity-agent">'
        + '<div class="activity-agent-name">' + escapeHtml(a.agent_name) + '</div>'
        + '<div class="activity-agent-stats">'
        + '<span>调用: <strong>' + a.total_calls + '</strong></span>'
        + '<span>成功率: <strong>' + (a.success_rate * 100).toFixed(0) + '%</strong></span>'
        + '</div></div>';
    }).join('');
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = '<div class="empty"><div class="empty-icon">⚠️</div>加载失败</div>';
  }
}

async function loadTimeline() {
  var el = document.getElementById('timeline-panel');
  if (!el) return;
  try {
    var data = await fetchJSON('/api/timeline?limit=30');
    if (!data.events || !data.events.length) {
      el.innerHTML = '<div class="empty"><div class="empty-icon">📅</div>暂无事件</div>';
      return;
    }
    var html = data.events.map(function(e) {
      var detailJson = JSON.stringify(e.detail || {}).replace(/"/g, '&quot;');
      return '<div class="history-item" data-event-id="' + escapeHtml(e.event_id) + '" data-event-type="' + escapeHtml(e.type) + '" data-detail="' + detailJson + '" onclick="showTimelineDetail(this.dataset.eventType, JSON.parse(this.dataset.detail))">'
        + '<div class="history-top"><span>' + e.emoji + ' ' + escapeHtml(e.summary) + '</span>'
        + '<span class="history-time">' + timeAgo(e.timestamp) + '</span></div>'
        + '<span class="click-hint">👆 详情</span></div>';
    }).join('');
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = '<div class="empty"><div class="empty-icon">⚠️</div>加载失败</div>';
  }
}

function showTimelineDetail(eventType, detail) {
  var modal = document.getElementById('detail-modal');
  var title = document.getElementById('modal-title');
  var meta = document.getElementById('modal-meta');
  var body = document.getElementById('modal-body');
  
  if (eventType === 'hook_call') {
    title.textContent = '🔗 调用详情';
    meta.innerHTML = '';
    body.innerHTML = '<div class="modal-section"><div class="modal-section-title">基本信息</div>'
      + '<div class="modal-section-content">'
      + '调用: ' + escapeHtml(detail.hook_name) + '<br>'
      + 'Endpoint: ' + escapeHtml(detail.endpoint) + '<br>'
      + 'Agent: ' + escapeHtml(detail.agent_id || '未知') + '<br>'
      + 'Status: ' + escapeHtml(detail.status) + '<br>'
      + 'Latency: ' + detail.latency_ms + 'ms</div></div>'
      + '<div class="modal-section"><div class="modal-section-title">Topic</div>'
      + '<div class="modal-section-content">' + escapeHtml(detail.topic) + '</div></div>';
  } else if (eventType.startsWith('exploration_')) {
    title.textContent = detail.emoji || '🔍 探索详情';
    meta.innerHTML = '<span class="modal-meta-item">Quality: ' + (detail.quality_score || 'N/A') + '</span>';
    body.innerHTML = '<div class="modal-section"><div class="modal-section-title">探索信息</div>'
      + '<div class="modal-section-content">'
      + 'Topic: ' + escapeHtml(detail.topic) + '<br>'
      + 'Status: ' + escapeHtml(detail.status) + '<br>'
      + 'Steps: ' + detail.total_steps + '<br>'
      + 'Quality Score: ' + (detail.quality_score || 'N/A') + '</div></div>';
  } else if (eventType === 'insight') {
    title.textContent = '💡 Dream 洞察详情';
    meta.innerHTML = '<span class="modal-meta-item">Surprise: ' + (detail.surprise || 0) + '</span>'
      + '<span class="modal-meta-item">Novelty: ' + (detail.novelty || 0) + '</span>';
    body.innerHTML = '<div class="modal-section"><div class="modal-section-title">洞察信息</div>'
      + '<div class="modal-section-content">'
      + 'Type: ' + escapeHtml(detail.insight_type) + '<br>'
      + 'Source Topics: ' + escapeHtml((detail.source_topics || []).join(', ')) + '</div></div>'
      + '<div class="modal-section"><div class="modal-section-title">内容</div>'
      + '<div class="modal-section-content">' + escapeHtml(detail.content || '无内容') + '</div></div>';
  } else {
    title.textContent = '📋 事件详情';
    meta.innerHTML = '';
    body.innerHTML = '<div class="modal-section-content" style="font-family:var(--font-data);font-size:12px;">' + escapeHtml(JSON.stringify(detail, null, 2)) + '</div>';
  }
  
  modal.classList.add('active');
}

function refreshHookBoard() { loadHookBoard(); }
function refreshTimeline() { loadTimeline(); }