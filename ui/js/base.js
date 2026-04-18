var API_BASE = '';
var state = null;

function timeAgo(ts) {
  if (!ts) return '';
  var d = new Date(ts);
  var now = new Date();
  var diff = Math.floor((now - d) / 1000);
  if (diff < 60) return diff + '秒前';
  if (diff < 3600) return Math.floor(diff / 60) + '分钟前';
  if (diff < 86400) return Math.floor(diff / 3600) + '小时前';
  return Math.floor(diff / 86400) + '天前';
}

function scoreClass(score) {
  if (!score) return '';
  if (score >= 8) return 'score-high';
  if (score >= 5) return 'score-mid';
  return 'score-low';
}

function log(msg, type) {
  var el = document.getElementById('log-content');
  if (!el) return;
  var line = document.createElement('div');
  line.className = 'log-line';
  var ts = document.createElement('span');
  ts.className = 'log-ts';
  ts.textContent = new Date().toLocaleTimeString();
  var txt = document.createElement('span');
  txt.className = type === 'ok' ? 'log-ok' : type === 'error' ? 'log-error' : 'log-info';
  txt.textContent = msg;
  line.appendChild(ts);
  line.appendChild(txt);
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
}

function fetchJSON(url, opts) {
  return fetch(API_BASE + url, opts).then(function(r) { return r.json(); });
}

function refreshAll() {
  log('🔄 刷新数据...', 'info');
  loadState().then(function() {
    loadStats();
    loadQueue();
    loadHistory();
    if (currentView === 'graph') renderGraph();
    log('✅ 刷新完成', 'ok');
  }).catch(function(e) {
    log('❌ 刷新失败: ' + e.message, 'error');
  });
}

function loadState() {
  return fetchJSON('/api/curious/state').then(function(data) {
    state = data;
    return data;
  });
}

function loadStats() {
  if (!state) return;
  var topics = state.knowledge && state.knowledge.topics || {};
  var queue = state.curiosity_queue || [];
  var pending = queue.filter(function(q) { return q.status !== 'done'; });
  var known = Object.keys(topics).filter(function(k) { return topics[k].status === 'known'; });
  
  document.getElementById('stat-nodes').textContent = Object.keys(topics).length;
  document.getElementById('stat-known').textContent = known.length + ' 已知';
  document.getElementById('stat-pending').textContent = pending.length;
  document.getElementById('stat-log').textContent = (state.exploration_log || []).length;
}

function loadQueue() {
  var el = document.getElementById('queue-list');
  if (!el) return;
  if (!state) { el.innerHTML = '<div class="empty">加载中...</div>'; return; }
  var queue = state.curiosity_queue || [];
  var pending = queue.filter(function(q) { return q.status !== 'done'; });
  if (!pending.length) { el.innerHTML = '<div class="empty">好奇心队列为空</div>'; return; }
  var html = pending.slice(0, 20).map(function(q) {
    return '<div class="item" data-topic="' + escapeHtml(q.topic) + '">'
      + '<div class="item-header"><span class="item-title">' + escapeHtml(q.topic) + '</span>'
      + '<span class="item-score ' + scoreClass(q.score) + '">' + (q.score || '-').toFixed(1) + '</span></div>'
      + '<div class="item-reason">' + escapeHtml(q.reason || '') + '</div>'
      + '<div class="item-meta"><span>深度: ' + (q.depth || '-').toFixed(1) + '</span><span class="click-hint">点击查看</span></div>'
      + '<div class="item-actions"><button class="btn btn-danger btn-sm" onclick="deleteQueue(\'' + escapeJs(q.topic) + '\')">删除</button></div>'
      + '</div>';
  }).join('');
  el.innerHTML = html;
}

function loadHistory() {
  var el = document.getElementById('history-list');
  if (!el) return;
  if (!state) { el.innerHTML = '<div class="empty">加载中...</div>'; return; }
  var logArr = state.exploration_log || [];
  if (!logArr.length) { el.innerHTML = '<div class="empty">探索历史为空</div>'; return; }
  var html = logArr.slice(-20).reverse().map(function(h) {
    return '<div class="history-item" data-topic="' + escapeHtml(h.topic) + '">'
      + '<div class="history-top"><span class="history-title">' + escapeHtml(h.topic) + '</span>'
      + '<span class="history-time">' + timeAgo(h.timestamp) + '</span></div>'
      + '<div class="history-findings">' + escapeHtml(h.findings || '').slice(0, 150) + '...</div>'
      + (h.notified ? '<div class="history-notified">已通知 R1D3</div>' : '')
      + '<span class="click-hint">点击查看详情</span></div>';
  }).join('');
  el.innerHTML = html;
}

function escapeHtml(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function escapeJs(s) {
  if (!s) return '';
  return String(s).replace(/\\/g,'\\\\').replace(/'/g,"\\'");
}

var currentView = 'list';

function switchView(view) {
  currentView = view;
  var tabs = document.querySelectorAll('.view-tab');
  tabs.forEach(function(t) {
    var v = t.getAttribute('data-view');
    t.classList.toggle('active', v === view);
  });
  var containers = document.querySelectorAll('.view-container');
  containers.forEach(function(c) {
    var v = c.id.replace('-view', '');
    c.classList.toggle('active', v === view);
    c.style.display = v === view ? 'block' : 'none';
  });
  if (view === 'graph') setTimeout(renderGraph, 100);
  if (view === 'internal') loadInternalView && loadInternalView();
  if (view === 'external') loadExternalView && loadExternalView();
}

function deleteQueue(topic) {
  if (!confirm('确认删除好奇心: ' + topic + '?')) return;
  fetchJSON('/api/curious/queue?topic=' + encodeURIComponent(topic), { method: 'DELETE' })
    .then(function(r) {
      if (r.status === 'success') {
        log('✅ 已删除: ' + topic, 'ok');
        refreshAll();
      } else {
        log('❌ 删除失败', 'error');
      }
    }).catch(function(e) {
      log('❌ 删除失败: ' + e.message, 'error');
    });
}

function injectTopic() {
  var topic = document.getElementById('inject-topic').value.trim();
  if (!topic) { log('⚠️ 请输入话题', 'error'); return; }
  var score = parseFloat(document.getElementById('inject-score').value) || 7;
  var depth = parseFloat(document.getElementById('inject-depth').value) || 6;
  var reason = document.getElementById('inject-reason').value.trim() || '手动注入';
  
  fetchJSON('/api/curious/inject', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic: topic, score: score, depth: depth, reason: reason })
  }).then(function(r) {
    if (r.status === 'ok') {
      log('✅ 已注入: ' + topic + ' (score=' + r.score.toFixed(1) + ')', 'ok');
      document.getElementById('inject-topic').value = '';
      refreshAll();
    } else {
      log('❌ 注入失败: ' + (r.error || '未知错误'), 'error');
    }
  }).catch(function(e) {
    log('❌ 注入失败: ' + e.message, 'error');
  });
}

function runExplore() {
  log('▶ 启动探索...', 'info');
  fetchJSON('/api/curious/run', { method: 'POST' })
    .then(function(r) {
      if (r.status === 'success') {
        log('✅ 探索完成: ' + r.topic, 'ok');
        refreshAll();
      } else if (r.status === 'idle') {
        log('⚠️ 队列为空', 'info');
      } else {
        log('❌ 探索失败: ' + (r.error || '未知错误'), 'error');
      }
    }).catch(function(e) {
      log('❌ 探索失败: ' + e.message, 'error');
    });
}

function closeModal() {
  document.getElementById('detail-modal').classList.remove('active');
}

function showDetail(type, id) {
  if (type === 'knowledge') {
    fetchJSON('/api/kg/nodes/' + encodeURIComponent(id)).then(function(node) {
      var modal = document.getElementById('detail-modal');
      var title = document.getElementById('modal-title');
      var meta = document.getElementById('modal-meta');
      var body = document.getElementById('modal-body');
      
      title.textContent = '📚 ' + id;
      meta.innerHTML = '<span class="modal-meta-item">质量: ' + (node.quality || '-') + '</span>'
        + '<span class="modal-meta-item">状态: ' + (node.status || '未探索') + '</span>'
        + '<span class="modal-meta-item">深度: ' + (node.depth || 5) + '</span>';
      
      var summaryText = node.summary || '暂无摘要';
      var summaryObj = null;
      try {
        summaryObj = JSON.parse(summaryText);
      } catch (e) {}
      
      var bodyHtml = '';
      
      if (summaryObj) {
        // 概述
        if (summaryObj.summary) {
          bodyHtml += '<div class="modal-section"><div class="modal-section-title">📖 概述</div>'
            + '<div class="modal-section-content">' + escapeHtml(summaryObj.summary) + '</div></div>';
        }
        
        // 关键要点
        if (summaryObj.key_points && summaryObj.key_points.length > 0) {
          bodyHtml += '<div class="modal-section"><div class="modal-section-title">💡 关键要点</div>'
            + '<ul class="modal-sources">' + summaryObj.key_points.map(function(kp) {
              return '<li>' + escapeHtml(kp) + '</li>';
            }).join('') + '</ul></div>';
        }
        
        // 技术栈/标签
        if (summaryObj.tech_stack && summaryObj.tech_stack.length > 0) {
          bodyHtml += '<div class="modal-section"><div class="modal-section-title">🔧 技术栈</div>'
            + '<div class="modal-section-content">'
            + summaryObj.tech_stack.map(function(ts) { return '<span style="display:inline-block;padding:2px 8px;margin:2px;background:var(--bg);border:1px solid var(--border);border-radius:4px;font-size:12px;">' + escapeHtml(ts) + '</span>'; }).join(' ')
            + '</div></div>';
        }
        
        // 应用场景
        if (summaryObj.use_cases && summaryObj.use_cases.length > 0) {
          bodyHtml += '<div class="modal-section"><div class="modal-section-title">🎯 应用场景</div>'
            + '<ul class="modal-sources">' + summaryObj.use_cases.map(function(uc) {
              return '<li>' + escapeHtml(uc) + '</li>';
            }).join('') + '</ul></div>';
        }
        
        // 参考资料
        if (summaryObj.references && summaryObj.references.length > 0) {
          bodyHtml += '<div class="modal-section"><div class="modal-section-title">📚 参考资料</div>'
            + '<ul class="modal-sources">' + summaryObj.references.map(function(ref) {
              if (typeof ref === 'string') {
                return '<li>' + escapeHtml(ref) + '</li>';
              } else if (ref.url) {
                return '<li><a href="' + escapeHtml(ref.url) + '" target="_blank">' + escapeHtml(ref.title || ref.url) + '</a></li>';
              }
              return '';
            }).join('') + '</ul></div>';
        }
        
        // 其他字段
        var extraFields = ['length', 'source', 'author', 'date', 'version', 'status', 'type', 'category'];
        var extraHtml = '';
        extraFields.forEach(function(field) {
          if (summaryObj[field] !== undefined && summaryObj[field] !== null) {
            extraHtml += '<span class="modal-meta-item">' + field + ': ' + escapeHtml(String(summaryObj[field])) + '</span>';
          }
        });
        if (extraHtml) {
          bodyHtml += '<div class="modal-section"><div class="modal-section-title">📋 其他信息</div>'
            + '<div class="modal-section-content">' + extraHtml + '</div></div>';
        }
      } else {
        // 普通文本summary
        bodyHtml = '<div class="modal-section"><div class="modal-section-title">📖 概述</div>'
          + '<div class="modal-section-content">' + escapeHtml(summaryText) + '</div></div>';
      }
      
      // 来源链接
      if (node.sources && node.sources.length > 0) {
        bodyHtml += '<div class="modal-section"><div class="modal-section-title">🔗 来源链接</div>'
          + '<ul class="modal-sources">' + node.sources.map(function(s) {
            return '<li><a href="' + escapeHtml(s) + '" target="_blank">' + escapeHtml(s) + '</a></li>';
          }).join('') + '</ul></div>';
      }
      
      body.innerHTML = bodyHtml || '<div class="empty">暂无内容</div>';
      modal.classList.add('active');
    });
  }
}

setInterval(refreshAll, 30000);
document.addEventListener('DOMContentLoaded', function() {
  refreshAll();
});