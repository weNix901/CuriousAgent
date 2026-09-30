// 关系类型配置：颜色 + 样式
var LINK_TYPE_CONFIG = {
  // 内置类型
  'decomposition': { color: '#58a6ff', width: 3, dash: '8,4', label: '分解关系', builtin: true },
  'cites':         { color: '#3fb950', width: 4, dash: '0',   label: '论文引用', builtin: true },
  'semantic':      { color: '#8b949e', width: 2, dash: '5,5', label: '语义相似', builtin: true },
  // 其他类型的默认样式（按需动态扩展）
  '_default_':     { color: '#8b949e', width: 2, dash: '0',   label: '其他关系', builtin: false }
};

// 动态发现的关系类型
var _g = { sim: null, link: null, nodeSel: null, data: null, W: 900, H: 960, linkTypes: {}, activeTypes: {} };

function buildGraphData() {
  if (!state) return { nodes: [], links: [] };
  var topics = state.knowledge && state.knowledge.topics || {};
  var topicsEntries = Object.entries(topics);
  var queue = state.curiosity_queue || [];
  var qMap = {};
  queue.forEach(function(q) { if (q.status !== 'done') qMap[q.topic.toLowerCase()] = true; });

  var nodes = topicsEntries.map(function(item) {
    var name = item[0], v = item[1], inQ = !!qMap[name.toLowerCase()];
    var score = 0;
    if (inQ) for (var i = 0; i < queue.length; i++) if (queue[i].topic === name) { score = queue[i].score || 0; break; }
    var q = typeof v.quality === 'number' ? v.quality : 0;
    var c = v.completeness_score || 0;
    var valueScore = q * (0.5 + c * 0.1);
    return { 
      id: name, 
      depth: v.depth || 0, 
      quality: v.quality, 
      score: score, 
      summary: v.summary || '', 
      sources: v.sources || [], 
      inQueue: inQ,
      completeness: v.completeness_score || 0,
      definition: v.definition || '',
      core: v.core || '',
      context: v.context || '',
      valueScore: valueScore
    };
  });

  var links = [], seen = {};

  // v0.3.3: Use Neo4j edges from API (all relationship types)
  var kgEdges = state.kg_edges || [];

  // 第一步：动态收集所有关系类型
  _g.linkTypes = {};
  kgEdges.forEach(function(e) {
    if (e.type && e.type !== 'DEPENDS_ON') {  // DEPENDS_ON 是内部关系，不显示
      _g.linkTypes[e.type] = true;
    }
  });

  // 第二步：为新类型生成配置（分配未使用颜色）
  var USED_COLORS = ['#58a6ff', '#3fb950', '#f85149', '#d29922', '#e040fb', '#ff7b72', '#79c0ff', '#7ee787'];
  var colorIdx = 0;
  for (var t in _g.linkTypes) {
    if (!LINK_TYPE_CONFIG[t]) {
      LINK_TYPE_CONFIG[t] = {
        color: USED_COLORS[colorIdx % USED_COLORS.length],
        width: 2,
        dash: '4,4',
        label: t,
        builtin: false
      };
      colorIdx++;
    }
  }

  // 第三步：构建连线数据
  kgEdges.forEach(function(e) {
    // Skip self-referencing and internal edges
    if (e.source === e.target) return;
    if (e.type === 'DEPENDS_ON') return;
    if (topics[e.source] && topics[e.target]) {
      var key = [e.source, e.target].sort().join('|');
      if (!seen[key]) {
        seen[key] = true;
        var type = e.type === 'DERIVED_FROM' ? 'decomposition' : (e.type || '_other_').toLowerCase();
        links.push({ source: e.source, target: e.target, type: type, rawType: e.type });
      }
    }
  });

  // Legacy: fallback to topics.children (标注为 decomposition)
  for (var parent in topics) {
    var children = (topics[parent] && topics[parent].children) || [];
    for (var i = 0; i < children.length; i++) {
      var child = children[i];
      if (topics[child]) {
        var key = [parent, child].sort().join('|');
        if (!seen[key]) {
          seen[key] = true;
          links.push({ source: parent, target: child, type: 'decomposition', rawType: 'DERIVED_FROM' });
        }
      }
    }
  }

  // Legacy cites
  for (var citing in topics) {
    var cites = (topics[citing] && topics[citing].cites) || [];
    for (var i = 0; i < cites.length; i++) {
      var cited = cites[i];
      var key = [citing, cited].sort().join('|');
      if (!seen[key] && topics[cited]) {
        links.push({ source: citing, target: cited, type: 'cites', rawType: 'CITES' });
        seen[key] = true;
      }
    }
  }

  // 初始化 activeTypes（默认全部显示）
  _g.activeTypes = {};
  for (var t in LINK_TYPE_CONFIG) {
    if (t === '_default_') continue;
    _g.activeTypes[t] = true;
  }

  // DISABLED: Semantic similarity links (title token overlap)
  // This generated 165+ noise links from simple word overlaps like "Long" matching unrelated topics.
  // DERIVED_FROM and CITES provide actual structured knowledge; token overlap does not.
  /*
  var STOP = ['in', 'for', 'the', 'and', 'of', 'to', 'a', 'based'];
  function tokens(s) { 
    var result = [];
    var parts = (s || '').toLowerCase().split(/[\s\-_:,]+/);
    parts.forEach(function(p) {
      if (p.length <= 2) return;
      if (STOP.indexOf(p) >= 0) return;
      result.push(p);
      for (var i = 0; i < p.length - 1; i++) {
        var c = p.charAt(i);
        if (c >= '\u4e00' && c <= '\u9fff') {
          for (var j = i + 1; j <= p.length && j <= i + 6; j++) {
            var sub = p.substring(i, j);
            if (sub.length >= 2 && STOP.indexOf(sub) < 0) {
              result.push(sub);
            }
          }
        }
      }
    });
    return result.filter(function(t, idx, arr) { return arr.indexOf(t) === idx; });
  }
  nodes.forEach(function(n) { n._t = {}; tokens(n.id).forEach(function(t) { n._t[t] = true; }); });

  for (var i = 0; i < nodes.length; i++) {
    for (var j = i + 1; j < nodes.length; j++) {
      var a = nodes[i], b = nodes[j];
      if (qMap[a.id.toLowerCase()] || qMap[b.id.toLowerCase()]) continue;
      var sh = 0;
      for (var t in a._t) if (b._t[t]) sh++;
      if (sh >= 1) {
        var k = [a.id, b.id].sort().join('|');
        if (!seen[k]) {
          seen[k] = true;
          links.push({ source: a.id, target: b.id, type: 'semantic', strength: sh });
        }
      }
    }
  }
  */

  return { nodes: nodes, links: links };
}

function nodeColor(d) {
  var q = d.quality;
  if (q === undefined || q === null) {
    var c = d.completeness || 0;
    if (c >= 4) return '#3fb950';
    if (c >= 2) return '#d29922';
    if (c >= 1) return '#f85149';
    return '#8b949e';
  }
  if (q >= 7) return '#3fb950';
  if (q >= 5) return '#d29922';
  return '#f85149';
}

function renderGraph() {
  if (typeof d3 === 'undefined') { console.log('D3 not loaded'); return; }
  var svg = d3.select('#graph-svg');
  if (!svg.node()) return;
  svg.selectAll('*').remove();
  
  // 如果 state 还没加载，先加载再渲染
  if (!state) {
    svg.append('text').attr('x', '50%').attr('y', '50%').attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'middle').attr('fill', '#8b949e').attr('font-size', '14px')
      .text('正在加载知识图谱...');
    loadState().then(function() {
      renderGraph();
    }).catch(function(e) {
      svg.selectAll('*').remove();
      svg.append('text').attr('x', '50%').attr('y', '50%').attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle').attr('fill', '#f85149').attr('font-size', '14px')
        .text('加载失败: ' + e.message);
    });
    return;
  }
  
  var data = buildGraphData();
  document.getElementById('graph-controls').style.display = data.nodes.length ? 'flex' : 'none';
  if (!data.nodes.length) {
    svg.append('text').attr('x', '50%').attr('y', '50%').attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'middle').attr('fill', '#8b949e').attr('font-size', '14px')
      .text('暂无知识节点，请先运行探索');
    return;
  }
  var W = (svg.node().parentElement && svg.node().parentElement.clientWidth) || 900;
  var H = 960;
  _g.W = W; _g.H = H;
  svg.attr('viewBox', '0 0 ' + W + ' ' + H);
  var g = svg.append('g');
  svg.call(d3.zoom().scaleExtent([0.2, 4]).on('zoom', function(e) { g.attr('transform', e.transform); }));

  var link = g.append('g').selectAll('line').data(data.links).enter().append('line').attr('class', 'graph-link')
    .attr('stroke', function(d) {
      var cfg = LINK_TYPE_CONFIG[d.type] || LINK_TYPE_CONFIG['_default_'];
      return cfg.color;
    })
    .attr('stroke-width', function(d) {
      var cfg = LINK_TYPE_CONFIG[d.type] || LINK_TYPE_CONFIG['_default_'];
      return cfg.width;
    })
    .attr('stroke-dasharray', function(d) {
      var cfg = LINK_TYPE_CONFIG[d.type] || LINK_TYPE_CONFIG['_default_'];
      return cfg.dash;
    })
    .attr('stroke-opacity', 0.7);

  var nodeSel = g.append('g').selectAll('.graph-node').data(data.nodes).enter().append('g').attr('class', 'graph-node')
    .call(d3.drag().on('start', function(e, d) { if (!e.active) _g.sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag', function(e, d) { d.fx = e.x; d.fy = e.y; })
      .on('end', function(e, d) { if (!e.active) _g.sim.alphaTarget(0); d.fx = null; d.fy = null; }))
    .on('click', function(e, d) { e.stopPropagation(); showDetail('knowledge', d.id); });

  nodeSel.append('circle').attr('r', function(d) { return d.inQueue ? Math.max(18, d.valueScore * 2.4) : Math.max(12, d.valueScore * 1.8); })
    .attr('fill', nodeColor).attr('fill-opacity', 1.0)
    .attr('stroke', function(d) { return d.inQueue ? '#fff' : 'none'; }).attr('stroke-width', function(d) { return d.inQueue ? 2 : 0; });

  nodeSel.append('text').attr('class', 'node-label').attr('dx', function(d) { return Math.max(20, d.valueScore * 2) + 4; }).attr('dy', 4)
    .text(function(d) { return d.id.length > 26 ? d.id.substring(0, 23) + '...' : d.id; });

  nodeSel.append('title').text(function(d) { 
    var info = d.id + '\n质量:' + (d.quality || '待探索') + ' | 完整性:' + (d.completeness || 0) + '/5 | 价值分:' + d.valueScore.toFixed(1);
    if (d.definition) info += '\n定义: ' + d.definition.slice(0, 50) + '...';
    return info;
  });

  var charge = parseInt(document.getElementById('ctrl-charge') && document.getElementById('ctrl-charge').value || '-280');
  var dist = parseInt(document.getElementById('ctrl-distance') && document.getElementById('ctrl-distance').value || '130');
  var stren = parseFloat(document.getElementById('ctrl-strength') && document.getElementById('ctrl-strength').value || '0.35');

  var sim = d3.forceSimulation(data.nodes)
    .force('link', d3.forceLink(data.links).id(function(d) { return d.id; }).distance(dist).strength(stren))
    .force('charge', d3.forceManyBody().strength(charge))
    .force('center', d3.forceCenter(W / 2, H / 2))
    .force('collision', d3.forceCollide().radius(function(d) { return Math.max(25, d.valueScore * 2.5) + 30; }))
    .on('tick', function() {
      link.attr('x1', function(d) { return d.source.x; }).attr('y1', function(d) { return d.source.y; })
        .attr('x2', function(d) { return d.target.x; }).attr('y2', function(d) { return d.target.y; });
      nodeSel.attr('transform', function(d) { return 'translate(' + d.x + ',' + d.y + ')'; });
    });

  _g.sim = sim; _g.link = link; _g.nodeSel = nodeSel; _g.data = data;
  buildLinkTypeControls();
  toggleLinkType();
  toggleLabels();
}

function applyGraphParams() {
  if (!_g.sim) return;
  var charge = parseInt(document.getElementById('ctrl-charge').value);
  var dist = parseInt(document.getElementById('ctrl-distance').value);
  var stren = parseFloat(document.getElementById('ctrl-strength').value);
  document.getElementById('lbl-charge').textContent = charge;
  document.getElementById('lbl-distance').textContent = dist;
  document.getElementById('lbl-strength').textContent = stren.toFixed(2);
  _g.sim.force('charge', d3.forceManyBody().strength(charge));
  _g.sim.force('link').distance(dist).strength(stren);
  _g.sim.alpha(0.5).restart();
}

function resetGraphLayout() {
  if (!_g.sim) return;
  _g.data.nodes.forEach(function(n) { n.x = _g.W / 2; n.y = _g.H / 2; n.vx = 0; n.vy = 0; });
  _g.sim.alpha(1.0).restart();
  log('🔄 图谱布局已重置', 'info');
}

function buildLinkTypeControls() {
  var container = document.getElementById('ctrl-link-types');
  if (!container) return;
  container.innerHTML = '';

  // 按 builtin 排序：builtin 类型在前
  var sortedTypes = Object.keys(_g.activeTypes).sort(function(a, b) {
    var ca = LINK_TYPE_CONFIG[a] && LINK_TYPE_CONFIG[a].builtin ? 0 : 1;
    var cb = LINK_TYPE_CONFIG[b] && LINK_TYPE_CONFIG[b].builtin ? 0 : 1;
    return ca - cb;
  });

  sortedTypes.forEach(function(type) {
    var cfg = LINK_TYPE_CONFIG[type] || LINK_TYPE_CONFIG['_default_'];
    var label = cfg.label || type;
    var checked = _g.activeTypes[type] !== false;
    var id = 'ctrl-link-' + type;

    var wrapper = document.createElement('label');
    wrapper.className = 'ctrl-check';
    wrapper.setAttribute('data-type', type);

    var checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.id = id;
    checkbox.checked = checked;
    checkbox.dataset.type = type;
    checkbox.onchange = function() {
      _g.activeTypes[this.dataset.type] = this.checked;
      toggleLinkType();
      updateLegend();
    };

    // 颜色指示点
    var dot = document.createElement('span');
    dot.style.display = 'inline-block';
    dot.style.width = '12px';
    dot.style.height = '3px';
    dot.style.background = cfg.color;
    dot.style.borderRadius = '2px';
    dot.style.marginRight = '4px';
    dot.style.verticalAlign = 'middle';

    wrapper.appendChild(checkbox);
    wrapper.appendChild(dot);
    wrapper.appendChild(document.createTextNode(label));
    container.appendChild(wrapper);
  });
}

function updateLegend() {
  var legend = document.getElementById('graph-legend');
  if (!legend) return;

  var allTypes = Object.keys(LINK_TYPE_CONFIG).filter(function(t) { return t !== '_default_'; });
  var visibleTypes = allTypes.filter(function(t) { return _g.activeTypes[t]; });

  var items = visibleTypes.map(function(type) {
    var cfg = LINK_TYPE_CONFIG[type];
    var dashStyle = cfg.dash && cfg.dash !== '0'
      ? 'border-top: ' + cfg.width + 'px ' + (cfg.dash.split(',')[1] > 3 ? 'dashed' : 'dotted') + ' ' + cfg.color
      : 'background:' + cfg.color;
    return '<div class="legend-item"><div class="legend-dot" style="' + dashStyle + '; width:14px; height:' + Math.max(cfg.width, 2) + 'px; border-radius:0;"></div>' + cfg.label + '</div>';
  }).join('');

  legend.innerHTML = items;
}

function toggleLinkType() {
  if (!_g.link) return;
  _g.link.attr('display', function(d) {
    if (_g.activeTypes[d.type] === false) return 'none';
    return null;
  });
}

function toggleLabels() {
  if (!_g.nodeSel) return;
  var show = document.getElementById('ctrl-show-labels').checked;
  _g.nodeSel.selectAll('text.node-label').attr('display', show ? null : 'none');
}