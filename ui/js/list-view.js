function renderCuriosity(queue) {
  var container = document.getElementById('curiosity-list');
  var pending = queue.filter(function(i) { return i.status === 'pending'; }).sort(function(a,b) { return b.score - a.score; });
  document.getElementById('queue-count').textContent = pending.length + ' 项';

  if (!pending.length) {
    container.innerHTML = '<div class="empty">好奇心队列为空，自动生成中...</div>';
    return;
  }

  container.innerHTML = pending.map(function(item) {
    return '<div class="item">'
      + '<div class="item-header"><div class="item-title">' + escapeHtml(item.topic) + '</div>'
      + '<span class="item-score ' + scoreClass(item.score) + '">' + item.score.toFixed(1) + '</span></div>'
      + '<div class="item-reason">→ ' + escapeHtml(item.reason) + '</div>'
      + '<div class="item-meta"><span>⏳ ' + item.status + '</span><span>📅 ' + timeAgo(item.created_at) + '</span></div>'
      + '<div class="item-actions" style="position:absolute;bottom:8px;right:8px;"><button class="btn btn-danger btn-sm" onclick="deleteQueueItem(' + item.id + ', \'' + escapeJs(item.topic) + '\')">删除</button></div>'
      + '</div>';
  }).join('');
}

function deleteQueueItem(itemId, topic) {
  if (!confirm('确定删除队列项 "' + topic + '" 吗？')) return;
  
  fetch('/api/queue/delete/' + itemId, {method: 'POST'})
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.status === 'ok') {
        loadState().then(function() { loadListView(); });
      } else {
        alert('删除失败: ' + (data.error || '未知错误'));
      }
    })
    .catch(function(e) {
      alert('请求失败: ' + e);
    });
}

function renderHistory(logs) {
  var container = document.getElementById('history-list');
  var recent = [].concat(logs).reverse().slice(0, 15);
  document.getElementById('history-count').textContent = recent.length + ' 条';

  if (!recent.length) {
    container.innerHTML = '<div class="empty">暂无探索记录</div>';
    return;
  }

  container.innerHTML = recent.map(function(item) {
    return '<div class="history-item" data-topic-key="' + escapeHtml(item.topic) + '" onclick="showDetail(\'history\',this.dataset.topicKey)">'
      + '<div class="history-top"><span class="history-title">' + escapeHtml(item.topic) + '</span>'
      + '<span class="history-time">' + timeAgo(item.timestamp) + '</span></div>'
      + '<div class="history-findings">' + escapeHtml(item.findings && item.findings.substring(0, 150)) + '...</div>'
      + '<div style="margin-top:4px;display:flex;align-items:center;">'
      + '<span style="font-size:11px;padding:2px 6px;background:var(--surface);border:1px solid var(--border);border-radius:4px;margin-right:6px">' + item.action + '</span>'
      + (item.notified_user ? '<span class="history-notified">📬 已通知</span>' : '')
      + '<span class="click-hint">👆 点击查看详情</span></div></div>';
  }).join('');
}

function renderKnowledge(topics) {
  var container = document.getElementById('knowledge-list');
  document.getElementById('knowledge-count').textContent = Object.keys(topics).length + ' 个';

  if (!Object.keys(topics).length) {
    container.innerHTML = '<div class="empty">暂无知识节点</div>';
    return;
  }

  var sorted = Object.entries(topics).sort(function(a,b) { return (b[1].depth || 5) - (a[1].depth || 5); });
  container.innerHTML = sorted.map(function(entry) {
    var topic = entry[0], v = entry[1];
    return '<div class="item" data-topic-key="' + escapeHtml(topic) + '" onclick="showDetail(\'knowledge\',this.dataset.topicKey)">'
      + '<div class="item-header"><div class="item-title">' + escapeHtml(topic) + '</div>'
      + '<span class="item-score ' + scoreClass((v.depth || 5) * 2) + '">' + depthLabel(v.depth || 5) + '</span></div>'
      + '<div class="item-reason">' + escapeHtml(v.summary && v.summary.substring(0, 100) || '—') + '</div>'
      + '<div class="item-meta"><span>🕐 ' + timeAgo(v.last_updated) + '</span>'
      + (v.sources && v.sources.length ? '<span>📚 ' + v.sources.length + ' 来源</span>' : '')
      + '<span class="click-hint">👆 详情</span></div></div>';
  }).join('');
}

function renderStats(data) {
  var topics = data.knowledge && data.knowledge.topics || {};
  var knownCount = Object.values(topics).filter(function(v) { return v.known; }).length;
  var pending = (data.curiosity_queue || []).filter(function(i) { return i.status === 'pending'; }).length;
  var notified = (data.exploration_log || []).filter(function(l) { return l.notified_user; }).length;

  document.getElementById('stat-nodes').textContent = Object.keys(topics).length;
  document.getElementById('stat-known').textContent = knownCount + ' 已知';
  document.getElementById('stat-pending').textContent = pending;
  document.getElementById('stat-history').textContent = (data.exploration_log || []).length;
  document.getElementById('stat-notified').textContent = notified + ' 已通知';
  document.getElementById('stat-last').textContent = data.last_update ? timeAgo(data.last_update) : '—';
}

function updateAlphaDisplay(value) {
  document.getElementById('alpha-value').textContent = value;
}

function setAlpha(value) {
  document.getElementById('alpha-slider').value = value;
  updateAlphaDisplay(value);
}

function injectCuriosity() {
  var topic = document.getElementById('inject-topic').value.trim();
  var rel = parseFloat(document.getElementById('inject-rel').value) || 7;
  var depth = parseFloat(document.getElementById('inject-depth').value) || 6;
  var reason = document.getElementById('inject-reason').value.trim() || '用户注入';
  var alpha = parseFloat(document.getElementById('alpha-slider').value) || 0.5;
  if (!topic) { alert('请输入话题'); return; }
  log('💉 注入好奇心: ' + topic + ' (α=' + alpha + ')', 'info');
  fetchJSON('/api/curious/inject', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic: topic, relevance: rel, depth: depth, reason: reason, alpha: alpha })
  }).then(function(r) {
    if (r.error) { log('❌ ' + r.error, 'error'); }
    else { log('✅ 注入成功', 'ok'); }
  }).catch(function(e) { log('❌ ' + e.message, 'error'); });
  document.getElementById('inject-topic').value = '';
  refreshAll();
}

function quickExplore(topic) {
  document.getElementById('inject-topic').value = topic;
  injectCuriosity();
  setTimeout(runExplore, 500);
}

function runExplore() {
  var btn = document.querySelector('.btn-primary');
  btn.disabled = true;
  btn.innerHTML = '<span class="loading"></span>探索中...';
  log('🚀 触发一轮探索...', 'info');
  fetchJSON('/api/curious/run', { method: 'POST' }).then(function(data) {
    if (data.error) {
      log('❌ 探索失败: ' + data.error, 'error');
    } else {
      log('✅ 探索完成: ' + data.topic, 'ok');
      if (data.findings) {
        log('📝 ' + data.findings.substring(0, 120) + '...', 'info');
      }
    }
  }).catch(function(e) {
    log('❌ 请求失败: ' + e.message, 'error');
  }).finally(function() {
    btn.disabled = false;
    btn.innerHTML = '▶ 运行探索';
    refreshAll();
  });
}

function loadMetaState() {
  fetchJSON('/api/metacognitive/state').then(function(data) {
    if (data.status === 'ok') {
      var summary = data.summary;
      document.getElementById('meta-completed').textContent = summary.completed_topics;
      document.getElementById('meta-total').textContent = summary.total_explorations;
      document.getElementById('meta-topics').textContent = summary.topics_with_history;
      document.getElementById('meta-status').textContent = '已更新';
      loadCompletedTopics();
    }
  }).catch(function(e) {
    console.error('Error loading meta state:', e);
  });
}

function loadCompletedTopics() {
  fetchJSON('/api/metacognitive/topics/completed').then(function(data) {
    var container = document.getElementById('completed-topics-list');
    if (!data.completed_topics.length) {
      container.innerHTML = '<div class="empty">暂无已完成话题</div>';
    } else {
      container.innerHTML = data.completed_topics.map(function(t) {
        return '<div class="item"><div class="item-header"><div class="item-title">' + escapeHtml(t.topic) + '</div></div>'
          + '<div class="item-reason">' + escapeHtml(t.reason) + '</div></div>';
      }).join('');
    }
  }).catch(function(e) {
    console.error('Error loading completed topics:', e);
  });
}

function loadListView() {
  if (!state) return;
  renderStats(state);
  renderCuriosity(state.curiosity_queue || []);
  renderHistory(state.exploration_log || []);
  renderKnowledge(state.knowledge && state.knowledge.topics || {});
  loadMetaState();
}