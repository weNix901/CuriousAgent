var bootstrapConfig = null;

var DEFAULT_TEMPLATES = {
  'kg-summary': '[CA Knowledge Summary]\n你最近探索的话题：\n{nodes_list}',
  'cognitive-framework': '[CA Cognitive Framework]\n回答知识问题时，先判断 KG 置信度：\n- 🟢 Expert (≥85%): 直接从 KG 知识回答，引用来源\n- 🟡 Intermediate (60-85%): KG 知识 + 搜索补充\n- 🟠 Beginner (30-60%): 先搜索，再回答，注入 CA 探索\n- 🔴 Novice (<30%): LLM 回答 + 必须注入 CA 探索',
  'skill-rules': '[CA Skill Rules]\n调用 knowledge-query Skill ONLY when:\n- ✅ 概念解释类："什么是 X"、"解释 Y"、"X 的原理"\n- ✅ 技术对比类："X 和 Y 的区别"\n- ❌ 命令执行类：直接执行，不查询 KG\n- ❌ 代码编写类：直接生成代码',
  'topic-extraction': '[Topic Extraction Rules]\n提取核心话题时：\n- 长度：2-10 字（名词短语）\n- 剔除："什么是"、"解释"、"怎么"、"帮我"'
};

async function loadExternalView() {
  await Promise.all([
    loadBootstrapConfig(),
    loadHookBoard(),
    loadAgentActivity(),
    loadTimeline()
  ]);
}

async function loadBootstrapConfig() {
  try {
    var data = await fetchJSON('/api/hooks/bootstrap/config');
    bootstrapConfig = data.config || getDefaultConfig();
    applyBootstrapConfig();
  } catch (e) {
    bootstrapConfig = getDefaultConfig();
    applyBootstrapConfig();
  }
}

function getDefaultConfig() {
  return {
    enabled: true,
    timeout_ms: 1500,
    max_nodes: 5,
    min_quality: 0,
    sort_by: 'created_at',
    injection_sections: {
      'kg-summary': { enabled: true, template: DEFAULT_TEMPLATES['kg-summary'] },
      'cognitive-framework': { enabled: true, template: DEFAULT_TEMPLATES['cognitive-framework'] },
      'skill-rules': { enabled: true, template: DEFAULT_TEMPLATES['skill-rules'] },
      'topic-extraction': { enabled: true, template: DEFAULT_TEMPLATES['topic-extraction'] }
    }
  };
}

function applyBootstrapConfig() {
  document.getElementById('bootstrap-enabled').checked = bootstrapConfig.enabled;
  document.getElementById('bootstrap-timeout').value = bootstrapConfig.timeout_ms;
  document.getElementById('bootstrap-timeout-val').textContent = bootstrapConfig.timeout_ms;
  document.getElementById('bootstrap-max-nodes').value = bootstrapConfig.max_nodes;
  document.getElementById('bootstrap-max-nodes-val').textContent = bootstrapConfig.max_nodes;
  document.getElementById('bootstrap-min-quality').value = bootstrapConfig.min_quality;
  document.getElementById('bootstrap-min-quality-val').textContent = bootstrapConfig.min_quality;
  document.getElementById('bootstrap-sort-by').value = bootstrapConfig.sort_by;
  
  var sections = bootstrapConfig.injection_sections || {};
  ['kg-summary', 'cognitive-framework', 'skill-rules', 'topic-extraction'].forEach(function(name) {
    var sec = sections[name] || { enabled: true, template: DEFAULT_TEMPLATES[name] };
    document.getElementById('section-' + name).checked = sec.enabled;
    document.getElementById('template-' + name + '-text').value = sec.template || DEFAULT_TEMPLATES[name];
  });
}

function updateSlider(id) {
  var input = document.getElementById(id);
  var val = document.getElementById(id + '-val');
  if (val) val.textContent = input.value;
}

function toggleSectionEdit(name) {
  var editDiv = document.getElementById('template-' + name);
  var checkbox = document.getElementById('section-' + name);
  if (editDiv) {
    editDiv.style.display = checkbox.checked ? 'none' : 'none';
  }
}

function editSectionTemplate(name) {
  var editDiv = document.getElementById('template-' + name);
  if (editDiv) {
    editDiv.style.display = editDiv.style.display === 'none' ? 'block' : 'none';
  }
}

function saveSectionTemplate(name) {
  var textarea = document.getElementById('template-' + name + '-text');
  var template = textarea.value;
  bootstrapConfig.injection_sections[name].template = template;
  showToast('模板已更新: ' + name, 'success');
}

async function saveBootstrapConfig() {
  var sections = {};
  ['kg-summary', 'cognitive-framework', 'skill-rules', 'topic-extraction'].forEach(function(name) {
    sections[name] = {
      enabled: document.getElementById('section-' + name).checked,
      template: document.getElementById('template-' + name + '-text').value
    };
  });
  
  var newConfig = {
    enabled: document.getElementById('bootstrap-enabled').checked,
    timeout_ms: parseInt(document.getElementById('bootstrap-timeout').value),
    max_nodes: parseInt(document.getElementById('bootstrap-max-nodes').value),
    min_quality: parseFloat(document.getElementById('bootstrap-min-quality').value),
    sort_by: document.getElementById('bootstrap-sort-by').value,
    injection_sections: sections
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
      showToast('⚠️ 保存失败: ' + (data.error || '未知错误'), 'error');
    }
  } catch (e) {
    showToast('⚠️ 保存失败: ' + e.message, 'error');
  }
}

function resetBootstrapConfig() {
  bootstrapConfig = getDefaultConfig();
  applyBootstrapConfig();
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
      var hookName = r.hook_name || r.endpoint.split('/').pop();
      var time = r.timestamp ? timeAgo(r.timestamp) : '';
      var notifiedBadge = r.knowledge_injected > 0 ? '<span class="badge badge-success">注入' + r.knowledge_injected + '</span>' : '';
      return '<div class="history-item" onclick="showHookDetail(\'' + r.id + '\')">'
        + '<div class="history-top"><span>' + emoji + ' ' + escapeHtml(hookName) + '</span>'
        + '<span class="history-time">' + time + ' | ' + r.latency_ms + 'ms</span></div>'
        + '<div class="history-findings">' + escapeHtml(r.endpoint) + ' → ' + r.status_code + ' ' + notifiedBadge + '</div>'
        + '<span class="click-hint">👆 详情</span></div>';
    }).join('');
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = '<div class="empty"><div class="empty-icon">⚠️</div>加载失败</div>';
  }
}

async function showHookDetail(hookId) {
  var modal = document.getElementById('detail-modal');
  var title = document.getElementById('modal-title');
  var meta = document.getElementById('modal-meta');
  var body = document.getElementById('modal-body');
  
  try {
    var data = await fetchJSON('/api/audit/hooks/' + hookId);
    var hookDisplay = data.hook_name !== 'unknown' ? data.hook_name : data.endpoint;
    
    title.textContent = '🤖 ' + hookDisplay;
    meta.innerHTML = '<span class="modal-meta-item">时间: ' + timeAgo(data.timestamp) + '</span>'
      + '<span class="modal-meta-item">耗时: ' + data.latency_ms + 'ms</span>'
      + '<span class="modal-meta-item">状态: ' + data.status + '</span>';
    if (data.knowledge_injected > 0) {
      meta.innerHTML += '<span class="modal-meta-item badge badge-success">注入 ' + data.knowledge_injected + ' 节点</span>';
    }
    
    var bodyHtml = '<div class="modal-section"><div class="modal-section-title">基本信息</div>'
      + '<div class="modal-section-content">Endpoint: ' + escapeHtml(data.endpoint) + '<br>Method: ' + data.method + '<br>Agent: ' + data.agent_id + '<br>Status Code: ' + data.status_code + '</div></div>';
    
    if (data.hook_name === 'knowledge-bootstrap-hook' && data.response_payload) {
      try {
        var resp = JSON.parse(data.response_payload);
        var nodes = resp.nodes || [];
        var edges = resp.edges || [];
        bodyHtml += '<div class="modal-section"><div class="modal-section-title">注入内容</div>'
          + '<div class="modal-section-content">节点: ' + nodes.length + ' | 关系: ' + edges.length + '</div></div>';
        if (nodes.length > 0) {
          var topNodes = nodes.slice(0, 5).map(function(n, i) {
            return '<div>' + (i+1) + '. ' + escapeHtml(n.id || n.topic) + ' (quality: ' + (n.quality || 'N/A') + ')</div>';
          }).join('');
          bodyHtml += '<div class="modal-section"><div class="modal-section-title">Top 5 节点</div><div class="modal-section-content">' + topNodes + '</div></div>';
        }
      } catch (parseErr) {
        bodyHtml += '<div class="modal-section"><div class="modal-section-title">响应</div>'
          + '<div class="modal-section-content" style="max-height:200px;overflow-y:auto;font-family:var(--font-data);font-size:12px;">' + escapeHtml(data.response_payload) + '</div></div>';
      }
    } else {
      bodyHtml += '<div class="modal-section"><div class="modal-section-title">响应</div>'
        + '<div class="modal-section-content" style="max-height:200px;overflow-y:auto;font-family:var(--font-data);font-size:12px;">' + escapeHtml(data.response_payload || '无响应') + '</div></div>';
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
        + '<div class="activity-agent-stats">调用: <strong>' + a.total_calls + '</strong> 成功率: <strong>' + (a.success_rate * 100).toFixed(0) + '%</strong></div></div>';
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
      return '<div class="history-item" onclick="showTimelineDetail(\'' + e.type + '\',\'' + JSON.stringify(e.detail || {}).replace(/'/g, "\\'") + '\')">'
        + '<div class="history-top"><span>' + (e.emoji || '📋') + ' ' + escapeHtml(e.summary) + '</span>'
        + '<span class="history-time">' + timeAgo(e.timestamp) + '</span></div>'
        + '<span class="click-hint">👆 详情</span></div>';
    }).join('');
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = '<div class="empty"><div class="empty-icon">⚠️</div>加载失败</div>';
  }
}

function showTimelineDetail(type, detailStr) {
  var modal = document.getElementById('detail-modal');
  var title = document.getElementById('modal-title');
  var meta = document.getElementById('modal-meta');
  var body = document.getElementById('modal-body');
  
  try {
    var detail = JSON.parse(detailStr);
    title.textContent = type + ' 详情';
    meta.innerHTML = '';
    body.innerHTML = '<div class="modal-section-content" style="font-family:var(--font-data);font-size:12px;">' + escapeHtml(JSON.stringify(detail, null, 2)) + '</div>';
    modal.classList.add('active');
  } catch (e) {
    showToast('解析失败', 'error');
  }
}

function refreshHookBoard() { loadHookBoard(); }
function refreshTimeline() { loadTimeline(); }