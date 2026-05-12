var trustedSources = [];

function loadSources() {
  fetchJSON('/api/trusted-sources')
    .then(function(data) {
      trustedSources = data.sources || [];
      renderSourcesTable();
    })
    .catch(function(e) {
      console.error('Failed to load trusted sources:', e);
      showToast('加载可信数据源失败', 'error');
    });
}

function renderSourcesTable() {
  var tbody = document.getElementById('sources-table-body');
  var emptyDiv = document.getElementById('sources-empty');

  if (!trustedSources.length) {
    tbody.innerHTML = '';
    emptyDiv.style.display = 'block';
    return;
  }

  emptyDiv.style.display = 'none';

  var html = trustedSources.map(function(source) {
    var typeClass = 'type-' + (source.type || 'other');
    var trustClass = 'trust-' + (source.trust_level || 'medium');
    var statusClass = source.enabled ? 'status-enabled' : 'status-disabled';
    var statusText = source.enabled ? '✅ 启用' : '⏸️ 禁用';
    var toggleBtnText = source.enabled ? '禁用' : '启用';
    var toggleBtnClass = source.enabled ? 'btn-danger' : 'btn-success';

    return '<tr>'
      + '<td class="domain-cell">' + escapeHtml(source.domain) + '</td>'
      + '<td>' + escapeHtml(source.name) + '</td>'
      + '<td><span class="type-badge ' + typeClass + '">' + getTypeLabel(source.type) + '</span></td>'
      + '<td class="' + trustClass + '">' + getTrustLabel(source.trust_level) + '</td>'
      + '<td class="' + statusClass + '">' + statusText + '</td>'
      + '<td>'
      + '<button class="btn btn-sm ' + toggleBtnClass + '" onclick="toggleSource(\'' + escapeJs(source.domain) + '\')">' + toggleBtnText + '</button>'
      + '<button class="btn btn-sm btn-danger" style="margin-left: var(--space-2);" onclick="deleteSource(\'' + escapeJs(source.domain) + '\')">删除</button>'
      + '</td>'
      + '</tr>';
  }).join('');

  tbody.innerHTML = html;
}

function getTypeLabel(type) {
  var labels = {
    academic: '学术论文',
    documentation: '技术文档',
    github: 'GitHub',
    blog: '技术博客',
    news: '新闻资讯',
    other: '其他'
  };
  return labels[type] || '其他';
}

function getTrustLabel(level) {
  var labels = {
    high: '高',
    medium: '中',
    low: '低'
  };
  return labels[level] || '中';
}

function checkUrl() {
  var urlInput = document.getElementById('check-url-input');
  var url = urlInput.value.trim();

  if (!url) {
    showToast('请输入 URL', 'error');
    return;
  }

  var resultDiv = document.getElementById('check-result');
  var resultIcon = document.getElementById('check-result-icon');
  var resultText = document.getElementById('check-result-text');

  resultDiv.style.display = 'block';
  resultIcon.textContent = '⏳';
  resultText.textContent = '检查中...';

  fetchJSON('/api/trusted-sources/check?url=' + encodeURIComponent(url))
    .then(function(data) {
      if (data.trusted) {
        resultIcon.textContent = '✅';
        resultText.innerHTML = '<strong>可信</strong> - ' + escapeHtml(data.domain || '')
          + ' (等级: ' + getTrustLabel(data.trust_level) + ')';
        resultDiv.style.background = 'var(--success-light)';
        resultDiv.style.borderColor = 'var(--success)';
      } else {
        resultIcon.textContent = '❌';
        resultText.innerHTML = '<strong>不可信</strong> - 该域名不在可信列表中';
        resultDiv.style.background = 'var(--error-light)';
        resultDiv.style.borderColor = 'var(--error)';
      }
    })
    .catch(function(e) {
      resultIcon.textContent = '⚠️';
      resultText.textContent = '检查失败: ' + e.message;
      resultDiv.style.background = 'var(--warning-light)';
      resultDiv.style.borderColor = 'var(--warning)';
    });
}

function addSource(event) {
  event.preventDefault();

  var domain = document.getElementById('source-domain').value.trim();
  var name = document.getElementById('source-name').value.trim();
  var type = document.getElementById('source-type').value;
  var trustLevel = document.getElementById('source-trust-level').value;

  if (!domain || !name) {
    showToast('请填写完整信息', 'error');
    return;
  }

  var source = {
    domain: domain,
    name: name,
    type: type,
    trust_level: trustLevel,
    enabled: true
  };

  fetchJSON('/api/trusted-sources', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(source)
  })
    .then(function(data) {
      if (data.status === 'success' || data.status === 'ok') {
        showToast('数据源添加成功', 'success');
        document.getElementById('add-source-form').reset();
        loadSources();
      } else {
        showToast('添加失败: ' + (data.error || '未知错误'), 'error');
      }
    })
    .catch(function(e) {
      showToast('添加失败: ' + e.message, 'error');
    });
}

function toggleSource(domain) {
  fetchJSON('/api/trusted-sources/' + encodeURIComponent(domain) + '/toggle', {
    method: 'POST'
  })
    .then(function(data) {
      if (data.status === 'success' || data.status === 'ok') {
        showToast('状态已更新', 'success');
        loadSources();
      } else {
        showToast('更新失败: ' + (data.error || '未知错误'), 'error');
      }
    })
    .catch(function(e) {
      showToast('更新失败: ' + e.message, 'error');
    });
}

function deleteSource(domain) {
  if (!confirm('确定要删除数据源 "' + domain + '" 吗？')) {
    return;
  }

  fetchJSON('/api/trusted-sources/' + encodeURIComponent(domain), {
    method: 'DELETE'
  })
    .then(function(data) {
      if (data.status === 'success' || data.status === 'ok') {
        showToast('数据源已删除', 'success');
        loadSources();
      } else {
        showToast('删除失败: ' + (data.error || '未知错误'), 'error');
      }
    })
    .catch(function(e) {
      showToast('删除失败: ' + e.message, 'error');
    });
}

function exportSources() {
  if (!trustedSources.length) {
    showToast('没有可导出的数据源', 'error');
    return;
  }

  var data = {
    version: '1.0',
    exported_at: new Date().toISOString(),
    sources: trustedSources
  };

  var blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = 'trusted-sources-' + new Date().toISOString().slice(0, 10) + '.json';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  showToast('数据源已导出', 'success');
}

function importSources() {
  var fileInput = document.getElementById('import-file');
  var file = fileInput.files[0];

  if (!file) {
    return;
  }

  var reader = new FileReader();
  reader.onload = function(e) {
    try {
      var data = JSON.parse(e.target.result);
      var sources = data.sources || data;

      if (!Array.isArray(sources) || !sources.length) {
        showToast('文件格式无效', 'error');
        return;
      }

      var imported = 0;
      var failed = 0;

      sources.forEach(function(source) {
        if (!source.domain || !source.name) {
          failed++;
          return;
        }

        fetchJSON('/api/trusted-sources', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            domain: source.domain,
            name: source.name,
            type: source.type || 'other',
            trust_level: source.trust_level || 'medium',
            enabled: source.enabled !== false
          })
        })
          .then(function() {
            imported++;
            if (imported + failed === sources.length) {
              showToast('导入完成: ' + imported + ' 成功, ' + failed + ' 失败', 'success');
              loadSources();
            }
          })
          .catch(function() {
            failed++;
            if (imported + failed === sources.length) {
              showToast('导入完成: ' + imported + ' 成功, ' + failed + ' 失败', 'success');
              loadSources();
            }
          });
      });
    } catch (err) {
      showToast('文件解析失败: ' + err.message, 'error');
    }
  };
  reader.readAsText(file);
  fileInput.value = '';
}

document.addEventListener('DOMContentLoaded', function() {
  if (document.getElementById('sources-table-body')) {
    loadSources();
  }
});
