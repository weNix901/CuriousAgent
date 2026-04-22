var _g = { sim: null, link: null, nodeSel: null, data: null, W: 900, H: 960 };

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
      context: v.context || ''
    };
  });

  var links = [], seen = {};

  for (var parent in topics) {
    var children = (topics[parent] && topics[parent].children) || [];
    for (var i = 0; i < children.length; i++) {
      var child = children[i];
      if (topics[child]) {
        links.push({ source: parent, target: child, type: 'decomposition' });
        seen[[parent, child].sort().join('|')] = true;
      }
    }
  }

  for (var citing in topics) {
    var cites = (topics[citing] && topics[citing].cites) || [];
    for (var i = 0; i < cites.length; i++) {
      var cited = cites[i];
      var key = [citing, cited].sort().join('|');
      if (!seen[key] && topics[cited]) {
        links.push({ source: citing, target: cited, type: 'cites' });
        seen[key] = true;
      }
    }
  }

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

  return { nodes: nodes, links: links };
}

function nodeColor(d) {
  var q = d.quality;
  if (q === undefined || q === null) return '#8b949e';
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
      if (d.type === 'cites') return '#3fb950';
      if (d.type === 'decomposition') return '#58a6ff';
      return '#8b949e';
    })
    .attr('stroke-width', function(d) {
      if (d.type === 'cites') return 4;
      if (d.type === 'decomposition') return 3;
      return 2;
    })
    .attr('stroke-dasharray', function(d) {
      if (d.type === 'decomposition') return '8,4';
      if (d.type === 'semantic') return '5,5';
      return '0';
    })
    .attr('stroke-opacity', 0.7);

  var nodeSel = g.append('g').selectAll('.graph-node').data(data.nodes).enter().append('g').attr('class', 'graph-node')
    .call(d3.drag().on('start', function(e, d) { if (!e.active) _g.sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag', function(e, d) { d.fx = e.x; d.fy = e.y; })
      .on('end', function(e, d) { if (!e.active) _g.sim.alphaTarget(0); d.fx = null; d.fy = null; }))
    .on('click', function(e, d) { e.stopPropagation(); showDetail('knowledge', d.id); });

  nodeSel.append('circle').attr('r', function(d) { return d.inQueue ? Math.max(18, d.depth * 2.4) : Math.max(12, d.depth * 1.8); })
    .attr('fill', nodeColor).attr('fill-opacity', 1.0)
    .attr('stroke', function(d) { return d.inQueue ? '#fff' : 'none'; }).attr('stroke-width', function(d) { return d.inQueue ? 2 : 0; });

  nodeSel.append('text').attr('class', 'node-label').attr('dx', function(d) { return Math.max(20, d.depth * 2) + 4; }).attr('dy', 4)
    .text(function(d) { return d.id.length > 26 ? d.id.substring(0, 23) + '...' : d.id; });

  nodeSel.append('title').text(function(d) { 
    var info = d.id + '\n质量:' + (d.quality || '待探索') + ' | 完整性:' + (d.completeness || 0) + '/5';
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
    .force('collision', d3.forceCollide().radius(function(d) { return Math.max(25, d.depth * 2.5) + 30; }))
    .on('tick', function() {
      link.attr('x1', function(d) { return d.source.x; }).attr('y1', function(d) { return d.source.y; })
        .attr('x2', function(d) { return d.target.x; }).attr('y2', function(d) { return d.target.y; });
      nodeSel.attr('transform', function(d) { return 'translate(' + d.x + ',' + d.y + ')'; });
    });

  _g.sim = sim; _g.link = link; _g.nodeSel = nodeSel; _g.data = data;
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

function toggleLinkType() {
  if (!_g.link) return;
  var showDecomp = document.getElementById('ctrl-show-decomp').checked;
  var showCites = document.getElementById('ctrl-show-cites').checked;
  var showSem = document.getElementById('ctrl-show-semantic').checked;
  _g.link.attr('display', function(d) {
    if (d.type === 'decomposition' && !showDecomp) return 'none';
    if (d.type === 'cites' && !showCites) return 'none';
    if (d.type === 'semantic' && !showSem) return 'none';
    return null;
  });
}

function toggleLabels() {
  if (!_g.nodeSel) return;
  var show = document.getElementById('ctrl-show-labels').checked;
  _g.nodeSel.selectAll('text.node-label').attr('display', show ? null : 'none');
}