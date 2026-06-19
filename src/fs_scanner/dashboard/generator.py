"""HTML dashboard generator with embedded D3.js visualizations."""

from __future__ import annotations

import json
from pathlib import Path

from ..catalog.models import ScanResult
from ..reporters.terminal import format_size


_ASSETS_DIR = Path(__file__).parent / "assets"


def generate_dashboard(result: ScanResult, history: list[ScanResult] | None = None) -> str:
    """Generate a self-contained HTML dashboard with embedded D3.js.

    The output file contains:
    - D3.js v7 minified inline
    - All scan data as JSON in a script tag
    - CSS embedded in style tags
    - Interactive treemap, pie chart, table, suggestions, heatmap, trend
    """
    # Load D3.js
    d3_path = _ASSETS_DIR / "d3.min.js"
    d3_js = d3_path.read_text(encoding="utf-8") if d3_path.exists() else ""

    # Prepare data for embedding
    scan_data = _prepare_scan_data(result, history)
    scan_json = json.dumps(scan_data, sort_keys=True)

    # Build HTML
    html = _HTML_PREFIX
    html += f"<script>{d3_js}</script>\n"
    html += f"<script>const SCAN_DATA = {scan_json};</script>\n"
    html += _CSS
    html += _HTML_BODY
    html += _DASHBOARD_JS
    html += _HTML_SUFFIX
    return html


def _prepare_scan_data(result: ScanResult, history: list[ScanResult] | None) -> dict:
    """Convert ScanResult into JSON-serializable data for the dashboard."""
    # Directory hierarchy for treemap
    dir_tree = _build_treemap_data(result)

    # Categories for pie chart
    categories = [
        {"name": cat.value, "size": stats.total_size, "count": stats.file_count, "pct": stats.percentage}
        for cat, stats in sorted(result.categories.items(), key=lambda x: x[1].total_size, reverse=True)
        if stats.file_count > 0
    ]

    # Top files for table
    top_files = sorted(result.files, key=lambda f: f.size, reverse=True)[:500]
    files_data = [
        {"path": f.path, "size": f.size, "category": f.category.value, "mtime": f.mtime}
        for f in top_files
    ]

    # Suggestions
    suggestions = [
        {"path": s.path, "size": s.size, "category": s.category,
         "reason": s.reason, "risk": s.risk_level.value}
        for s in result.suggestions
    ]

    # Heatmap data: group file sizes by month
    heatmap = _build_heatmap_data(result)

    # History for trend chart
    history_data = []
    if history:
        for h in history:
            history_data.append({"timestamp": h.timestamp, "total_size": h.total_size, "total_files": h.total_files})
    history_data.append({"timestamp": result.timestamp, "total_size": result.total_size, "total_files": result.total_files})

    return {
        "root": result.root,
        "timestamp": result.timestamp,
        "total_size": result.total_size,
        "total_files": result.total_files,
        "tree": dir_tree,
        "categories": categories,
        "files": files_data,
        "suggestions": suggestions,
        "heatmap": heatmap,
        "history": history_data,
    }


def _build_treemap_data(result: ScanResult) -> dict:
    """Build hierarchical tree structure for D3 treemap."""
    from collections import defaultdict
    tree: dict = {"name": result.root, "children": {}}

    for f in result.files:
        # Get path relative to root
        rel = f.path
        if rel.startswith(result.root):
            rel = rel[len(result.root):]
        rel = rel.lstrip("/")
        parts = rel.split("/")

        node = tree
        for part in parts[:-1]:
            if "children" not in node:
                node["children"] = {}
            if part not in node["children"]:
                node["children"][part] = {"name": part, "children": {}}
            node = node["children"][part]

        # Leaf file
        filename = parts[-1] if parts else f.path
        if "children" not in node:
            node["children"] = {}
        node["children"][filename] = {"name": filename, "value": f.size}

    # Convert dict-based children to list-based for D3
    return _convert_tree(tree)


def _convert_tree(node: dict) -> dict:
    """Convert dict-children to list-children recursively."""
    result = {"name": node["name"]}
    if "value" in node and "children" not in node:
        result["value"] = node["value"]
        return result
    if "children" in node:
        children = []
        for child in node["children"].values():
            children.append(_convert_tree(child))
        if children:
            result["children"] = children
        else:
            result["value"] = 0
    else:
        result["value"] = 0
    return result


def _build_heatmap_data(result: ScanResult) -> list[dict]:
    """Group files by modification month for heatmap visualization."""
    from datetime import datetime
    monthly: dict[str, dict] = {}

    for f in result.files:
        try:
            dt = datetime.fromtimestamp(f.mtime)
            key = dt.strftime("%Y-%m")
            if key not in monthly:
                monthly[key] = {"month": key, "size": 0, "count": 0, "ghost_count": 0, "ghost_size": 0}
            monthly[key]["size"] += f.size
            monthly[key]["count"] += 1
            # Ghost file: >50MB and >2 years old
            import time
            two_years_ago = time.time() - (2 * 365.25 * 86400)
            if f.size > 50 * 1024 * 1024 and f.mtime < two_years_ago:
                monthly[key]["ghost_count"] += 1
                monthly[key]["ghost_size"] += f.size
        except (OSError, ValueError):
            continue

    return sorted(monthly.values(), key=lambda x: x["month"])


_HTML_PREFIX = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>fs-scanner Dashboard</title>
"""

_HTML_SUFFIX = """
</body>
</html>
"""


_CSS = """<style>
:root { --bg: #0f0f1a; --panel: #1a1a2e; --border: #2a2a4a; --text: #e0e0e0; --accent: #00d4ff; --accent2: #7c3aed; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
.header { background: var(--panel); padding: 1.5rem 2rem; border-bottom: 1px solid var(--border); }
.header h1 { color: var(--accent); font-size: 1.5rem; margin-bottom: 0.5rem; }
.header .meta { color: #888; font-size: 0.9rem; }
.header .stats { display: flex; gap: 2rem; margin-top: 0.5rem; }
.header .stat { font-size: 1.2rem; font-weight: 600; }
.header .stat span { color: #888; font-size: 0.8rem; font-weight: 400; display: block; }
.tabs { display: flex; background: var(--panel); border-bottom: 1px solid var(--border); padding: 0 1rem; overflow-x: auto; }
.tab { padding: 0.8rem 1.5rem; cursor: pointer; border-bottom: 2px solid transparent; color: #888; transition: all 0.2s; white-space: nowrap; }
.tab:hover { color: var(--text); }
.tab.active { color: var(--accent); border-bottom-color: var(--accent); }
.content { padding: 1.5rem 2rem; max-width: 1800px; margin: 0 auto; }
.panel { display: none; }
.panel.active { display: block; }
#treemap-container, #pie-container { width: 100%; min-height: 500px; }
#treemap-container svg, #pie-container svg { width: 100%; height: 500px; }
.breadcrumb { margin-bottom: 1rem; color: #888; }
.breadcrumb span { cursor: pointer; color: var(--accent); }
.breadcrumb span:hover { text-decoration: underline; }
table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
th, td { padding: 0.6rem 1rem; text-align: left; border-bottom: 1px solid var(--border); }
th { background: var(--panel); cursor: pointer; user-select: none; position: sticky; top: 0; }
th:hover { color: var(--accent); }
tr:hover { background: rgba(0,212,255,0.05); }
.filters { display: flex; gap: 1rem; margin-bottom: 1rem; flex-wrap: wrap; }
.filters input, .filters select { background: var(--panel); border: 1px solid var(--border); color: var(--text); padding: 0.5rem 1rem; border-radius: 4px; font-size: 0.9rem; }
.filters input { min-width: 250px; }
.risk-safe { color: #4ade80; }
.risk-caution { color: #fbbf24; }
.risk-risky { color: #f87171; }
.heatmap-grid { display: flex; flex-wrap: wrap; gap: 3px; }
.heatmap-cell { width: 14px; height: 14px; border-radius: 2px; cursor: pointer; }
.heatmap-cell:hover { outline: 1px solid var(--accent); }
.trend-chart { width: 100%; height: 300px; }
.tooltip { position: absolute; background: var(--panel); border: 1px solid var(--border); padding: 0.5rem 0.8rem; border-radius: 4px; font-size: 0.8rem; pointer-events: none; z-index: 1000; }
@media (max-width: 1024px) { .content { padding: 1rem; } .header .stats { flex-wrap: wrap; gap: 1rem; } }
</style>
"""


_HTML_BODY = """</head>
<body>
<div class="header">
  <h1>fs-scanner Dashboard</h1>
  <div class="meta" id="scan-meta"></div>
  <div class="stats" id="scan-stats"></div>
</div>
<div class="tabs">
  <div class="tab active" data-panel="treemap">Treemap</div>
  <div class="tab" data-panel="categories">Categories</div>
  <div class="tab" data-panel="files">Top Files</div>
  <div class="tab" data-panel="suggestions">Suggestions</div>
  <div class="tab" data-panel="heatmap">Heatmap</div>
  <div class="tab" data-panel="trend">Trend</div>
</div>
<div class="content">
  <div class="panel active" id="panel-treemap">
    <div class="breadcrumb" id="treemap-breadcrumb"></div>
    <div id="treemap-container"></div>
  </div>
  <div class="panel" id="panel-categories">
    <div id="pie-container"></div>
    <table id="cat-table"><thead><tr><th>Category</th><th>Size</th><th>Files</th><th>%</th></tr></thead><tbody></tbody></table>
  </div>
  <div class="panel" id="panel-files">
    <div class="filters">
      <input type="text" id="file-search" placeholder="Search by filename...">
      <select id="file-cat-filter"><option value="">All Categories</option></select>
    </div>
    <table id="file-table"><thead><tr><th data-col="path">Path</th><th data-col="size">Size</th><th data-col="category">Category</th><th data-col="mtime">Modified</th></tr></thead><tbody></tbody></table>
  </div>
  <div class="panel" id="panel-suggestions">
    <div id="suggestions-container"></div>
  </div>
  <div class="panel" id="panel-heatmap">
    <h2 style="margin-bottom:1rem;color:var(--accent)">File Modification Heatmap</h2>
    <div id="heatmap-container"></div>
    <div id="heatmap-detail" style="margin-top:1rem"></div>
  </div>
  <div class="panel" id="panel-trend">
    <h2 style="margin-bottom:1rem;color:var(--accent)">Disk Usage Trend</h2>
    <div id="trend-container" class="trend-chart"></div>
  </div>
</div>
<div class="tooltip" id="tooltip" style="display:none"></div>
"""


_DASHBOARD_JS = """<script>
// Utility
function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024*1024) return (bytes/1024).toFixed(1) + ' KB';
  if (bytes < 1024*1024*1024) return (bytes/1024/1024).toFixed(1) + ' MB';
  if (bytes < 1024*1024*1024*1024) return (bytes/1024/1024/1024).toFixed(1) + ' GB';
  return (bytes/1024/1024/1024/1024).toFixed(1) + ' TB';
}
function formatDate(ts) {
  return new Date(ts * 1000).toLocaleDateString();
}
const D = SCAN_DATA;
const tooltip = document.getElementById('tooltip');

// Header
document.getElementById('scan-meta').textContent = 'Root: ' + D.root + ' | Scanned: ' + D.timestamp;
document.getElementById('scan-stats').innerHTML =
  '<div class="stat">' + formatSize(D.total_size) + '<span>Total Size</span></div>' +
  '<div class="stat">' + D.total_files.toLocaleString() + '<span>Files</span></div>' +
  '<div class="stat">' + D.categories.length + '<span>Categories</span></div>';

// Tabs
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('panel-' + tab.dataset.panel).classList.add('active');
    if (tab.dataset.panel === 'treemap' && !treemapDrawn) drawTreemap();
    if (tab.dataset.panel === 'categories' && !pieDrawn) drawPie();
    if (tab.dataset.panel === 'heatmap' && !heatmapDrawn) drawHeatmap();
    if (tab.dataset.panel === 'trend' && !trendDrawn) drawTrend();
  });
});

// === TREEMAP ===
let treemapDrawn = false;
function drawTreemap() {
  treemapDrawn = true;
  const container = document.getElementById('treemap-container');
  const width = container.clientWidth || 900;
  const height = 500;
  container.innerHTML = '';

  const root = d3.hierarchy(D.tree).sum(d => d.value || 0).sort((a, b) => b.value - a.value);
  const treemap = d3.treemap().size([width, height]).paddingInner(1).paddingOuter(2);
  treemap(root);

  const svg = d3.select(container).append('svg').attr('viewBox', `0 0 ${width} ${height}`);
  let current = root;
  const color = d3.scaleOrdinal(d3.schemeTableau10);
  const breadcrumb = document.getElementById('treemap-breadcrumb');

  function render(node) {
    current = node;
    svg.selectAll('*').remove();
    const leaves = node.children || [node];
    const g = svg.selectAll('g').data(leaves).join('g').attr('transform', d => `translate(${d.x0},${d.y0})`);
    g.append('rect')
      .attr('width', d => Math.max(0, d.x1 - d.x0))
      .attr('height', d => Math.max(0, d.y1 - d.y0))
      .attr('fill', (d, i) => color(i % 10))
      .attr('opacity', 0.8)
      .attr('rx', 2)
      .style('cursor', d => d.children ? 'pointer' : 'default')
      .on('click', (e, d) => { if (d.children) { treemap(d); render(d); } })
      .on('mouseover', (e, d) => { tooltip.style.display='block'; tooltip.textContent=d.data.name+': '+formatSize(d.value); })
      .on('mousemove', e => { tooltip.style.left=(e.pageX+10)+'px'; tooltip.style.top=(e.pageY-20)+'px'; })
      .on('mouseout', () => { tooltip.style.display='none'; });
    g.append('text')
      .attr('x', 4).attr('y', 14).attr('fill', '#fff').attr('font-size', '11px')
      .text(d => { const w = d.x1 - d.x0; return w > 40 ? d.data.name.slice(0, Math.floor(w/7)) : ''; });

    // Breadcrumb
    let path = []; let n = node;
    while (n) { path.unshift(n); n = n.parent; }
    breadcrumb.innerHTML = path.map((p, i) =>
      i < path.length - 1 ? `<span data-idx="${i}">${p.data.name}</span> / ` : p.data.name
    ).join('');
    breadcrumb.querySelectorAll('span').forEach(s => {
      s.addEventListener('click', () => { const idx = +s.dataset.idx; treemap(path[idx]); render(path[idx]); });
    });
  }
  treemap(root);
  render(root);
}
setTimeout(drawTreemap, 100);
</script>
<script>
// === PIE CHART ===
let pieDrawn = false;
function drawPie() {
  pieDrawn = true;
  const container = document.getElementById('pie-container');
  const width = 500, height = 500, radius = Math.min(width, height) / 2 - 40;
  container.innerHTML = '';
  const svg = d3.select(container).append('svg').attr('viewBox', `0 0 ${width} ${height}`)
    .append('g').attr('transform', `translate(${width/2},${height/2})`);
  const color = d3.scaleOrdinal(d3.schemeTableau10);
  const pie = d3.pie().value(d => d.size).sort(null);
  const arc = d3.arc().innerRadius(radius * 0.4).outerRadius(radius);
  const labelArc = d3.arc().innerRadius(radius * 0.75).outerRadius(radius * 0.75);
  const arcs = svg.selectAll('.arc').data(pie(D.categories)).join('g').attr('class', 'arc');
  arcs.append('path').attr('d', arc).attr('fill', (d, i) => color(i)).attr('opacity', 0.85)
    .on('mouseover', (e, d) => { tooltip.style.display='block'; tooltip.textContent=d.data.name+': '+formatSize(d.data.size)+' ('+d.data.pct.toFixed(1)+'%)'; })
    .on('mousemove', e => { tooltip.style.left=(e.pageX+10)+'px'; tooltip.style.top=(e.pageY-20)+'px'; })
    .on('mouseout', () => { tooltip.style.display='none'; });
  arcs.append('text').attr('transform', d => `translate(${labelArc.centroid(d)})`).attr('text-anchor', 'middle')
    .attr('fill', '#fff').attr('font-size', '11px').text(d => d.data.pct > 3 ? d.data.name : '');

  // Category table
  const tbody = document.querySelector('#cat-table tbody');
  tbody.innerHTML = D.categories.map(c =>
    `<tr><td>${c.name}</td><td>${formatSize(c.size)}</td><td>${c.count.toLocaleString()}</td><td>${c.pct.toFixed(1)}%</td></tr>`
  ).join('');
}
</script>
<script>
// === FILE TABLE ===
let fileData = D.files.slice();
let sortCol = 'size', sortAsc = false;

function renderFileTable() {
  const tbody = document.querySelector('#file-table tbody');
  const search = document.getElementById('file-search').value.toLowerCase();
  const catFilter = document.getElementById('file-cat-filter').value;
  let filtered = fileData.filter(f => {
    if (search && !f.path.toLowerCase().includes(search)) return false;
    if (catFilter && f.category !== catFilter) return false;
    return true;
  });
  filtered.sort((a, b) => {
    let va = a[sortCol], vb = b[sortCol];
    if (typeof va === 'string') { va = va.toLowerCase(); vb = vb.toLowerCase(); }
    return sortAsc ? (va > vb ? 1 : -1) : (va < vb ? 1 : -1);
  });
  tbody.innerHTML = filtered.slice(0, 200).map(f =>
    `<tr><td title="${f.path}">${f.path.length>80 ? '...'+f.path.slice(-77) : f.path}</td><td>${formatSize(f.size)}</td><td>${f.category}</td><td>${formatDate(f.mtime)}</td></tr>`
  ).join('');
}

// Populate category filter
const cats = [...new Set(D.files.map(f => f.category))].sort();
const sel = document.getElementById('file-cat-filter');
cats.forEach(c => { const o = document.createElement('option'); o.value = c; o.textContent = c; sel.appendChild(o); });

document.getElementById('file-search').addEventListener('input', renderFileTable);
document.getElementById('file-cat-filter').addEventListener('change', renderFileTable);
document.querySelectorAll('#file-table th').forEach(th => {
  th.addEventListener('click', () => {
    const col = th.dataset.col;
    if (sortCol === col) sortAsc = !sortAsc; else { sortCol = col; sortAsc = false; }
    renderFileTable();
  });
});
renderFileTable();
</script>
<script>
// === SUGGESTIONS ===
(function() {
  const container = document.getElementById('suggestions-container');
  if (!D.suggestions.length) { container.innerHTML = '<p style="color:#888">No suggestions available.</p>'; return; }
  let totalSize = D.suggestions.reduce((s, x) => s + x.size, 0);
  let html = `<p style="margin-bottom:1rem"><strong>Total reclaimable:</strong> ${formatSize(totalSize)}</p>`;
  html += '<table><thead><tr><th>Category</th><th>Path</th><th>Size</th><th>Risk</th><th>Reason</th></tr></thead><tbody>';
  D.suggestions.forEach(s => {
    const riskClass = 'risk-' + s.risk;
    html += `<tr><td>${s.category}</td><td title="${s.path}">${s.path.length>60?'...'+s.path.slice(-57):s.path}</td><td>${formatSize(s.size)}</td><td class="${riskClass}">${s.risk.toUpperCase()}</td><td>${s.reason}</td></tr>`;
  });
  html += '</tbody></table>';
  container.innerHTML = html;
})();
</script>
<script>
// === HEATMAP ===
let heatmapDrawn = false;
function drawHeatmap() {
  heatmapDrawn = true;
  const container = document.getElementById('heatmap-container');
  if (!D.heatmap.length) { container.innerHTML = '<p style="color:#888">No data for heatmap.</p>'; return; }
  const maxSize = Math.max(...D.heatmap.map(h => h.size));
  const colorScale = d3.scaleSequential(d3.interpolateYlOrRd).domain([0, maxSize]);
  let html = '<div style="display:flex;flex-wrap:wrap;gap:4px;align-items:end">';
  D.heatmap.forEach(h => {
    const ghost = h.ghost_count > 0 ? ' outline:2px solid #f87171;' : '';
    html += `<div style="text-align:center"><div class="heatmap-cell" style="background:${colorScale(h.size)};width:30px;height:30px;${ghost}" data-month="${h.month}" title="${h.month}: ${formatSize(h.size)} (${h.count} files)"></div><div style="font-size:9px;color:#888;margin-top:2px">${h.month.slice(2)}</div></div>`;
  });
  html += '</div>';
  if (D.heatmap.some(h => h.ghost_count > 0)) {
    const totalGhost = D.heatmap.reduce((s, h) => s + h.ghost_size, 0);
    html += `<p style="margin-top:1rem;color:#f87171">Ghost files (>50MB, >2yr old): ${formatSize(totalGhost)}</p>`;
  }
  container.innerHTML = html;
  container.querySelectorAll('.heatmap-cell').forEach(cell => {
    cell.addEventListener('click', () => {
      const m = cell.dataset.month;
      const detail = document.getElementById('heatmap-detail');
      const monthFiles = D.files.filter(f => { const d = new Date(f.mtime*1000); return d.toISOString().slice(0,7) === m; }).sort((a,b) => b.size - a.size).slice(0, 20);
      detail.innerHTML = `<h3 style="color:var(--accent);margin-bottom:0.5rem">Files modified in ${m}</h3><table><thead><tr><th>Path</th><th>Size</th></tr></thead><tbody>` +
        monthFiles.map(f => `<tr><td>${f.path}</td><td>${formatSize(f.size)}</td></tr>`).join('') + '</tbody></table>';
    });
  });
}
</script>
<script>
// === TREND CHART ===
let trendDrawn = false;
function drawTrend() {
  trendDrawn = true;
  const container = document.getElementById('trend-container');
  if (D.history.length < 2) { container.innerHTML = '<p style="color:#888">Need at least 2 scans for trend data. Run fs-scanner multiple times with --format json.</p>'; return; }
  const width = container.clientWidth || 800, height = 280;
  const margin = {top: 20, right: 30, bottom: 40, left: 70};
  container.innerHTML = '';
  const svg = d3.select(container).append('svg').attr('viewBox', `0 0 ${width} ${height}`);
  const data = D.history.map(h => ({date: new Date(h.timestamp), size: h.total_size}));
  const x = d3.scaleTime().domain(d3.extent(data, d => d.date)).range([margin.left, width - margin.right]);
  const y = d3.scaleLinear().domain([0, d3.max(data, d => d.size) * 1.1]).range([height - margin.bottom, margin.top]);
  svg.append('g').attr('transform', `translate(0,${height-margin.bottom})`).call(d3.axisBottom(x).ticks(5)).selectAll('text').attr('fill','#888');
  svg.append('g').attr('transform', `translate(${margin.left},0)`).call(d3.axisLeft(y).ticks(5).tickFormat(d => formatSize(d))).selectAll('text').attr('fill','#888');
  svg.selectAll('.domain, .tick line').attr('stroke', '#333');
  const line = d3.line().x(d => x(d.date)).y(d => y(d.size)).curve(d3.curveMonotoneX);
  svg.append('path').datum(data).attr('fill', 'none').attr('stroke', 'var(--accent)').attr('stroke-width', 2).attr('d', line);
  svg.selectAll('circle').data(data).join('circle').attr('cx', d => x(d.date)).attr('cy', d => y(d.size)).attr('r', 4).attr('fill', 'var(--accent)');
}
</script>
"""
