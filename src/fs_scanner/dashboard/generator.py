"""HTML dashboard generator with embedded D3.js visualizations."""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..catalog.models import ScanResult
from ..reporters.terminal import format_size


_ASSETS_DIR = Path(__file__).parent / "assets"


def generate_dashboard(result: ScanResult, history: list[ScanResult] | None = None) -> str:
    """Generate a self-contained HTML dashboard with embedded D3.js."""
    d3_path = _ASSETS_DIR / "d3.min.js"
    d3_js = d3_path.read_text(encoding="utf-8") if d3_path.exists() else ""

    scan_data = _prepare_scan_data(result, history)
    scan_json = json.dumps(scan_data, sort_keys=True)

    html = _HTML_HEAD
    html += f"<script>{d3_js}</script>\n"
    html += f"<script>const SCAN_DATA = {scan_json};</script>\n"
    html += _CSS
    html += "</head>\n<body>\n"
    html += _HTML_BODY
    html += _DASHBOARD_JS
    html += "\n</body>\n</html>"
    return html


def _prepare_scan_data(result: ScanResult, history: list[ScanResult] | None) -> dict:
    dir_tree = _build_treemap_data(result)
    categories = [
        {"name": cat.value, "size": stats.total_size, "count": stats.file_count, "pct": stats.percentage}
        for cat, stats in sorted(result.categories.items(), key=lambda x: x[1].total_size, reverse=True)
        if stats.file_count > 0
    ]
    top_files = sorted(result.files, key=lambda f: f.size, reverse=True)[:500]
    files_data = [
        {"path": f.path, "size": f.size, "category": f.category.value, "mtime": f.mtime}
        for f in top_files
    ]
    suggestions = [
        {"path": s.path, "size": s.size, "category": s.category,
         "reason": s.reason, "risk": s.risk_level.value}
        for s in result.suggestions
    ]
    heatmap = _build_heatmap_data(result)
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
    tree: dict = {"name": result.root, "children": {}}
    for f in result.files:
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
        filename = parts[-1] if parts else f.path
        if "children" not in node:
            node["children"] = {}
        node["children"][filename] = {"name": filename, "value": f.size}
    return _convert_tree(tree)


def _convert_tree(node: dict) -> dict:
    result = {"name": node["name"]}
    if "value" in node and "children" not in node:
        result["value"] = node["value"]
        return result
    if "children" in node:
        children = [_convert_tree(child) for child in node["children"].values()]
        if children:
            result["children"] = children
        else:
            result["value"] = 0
    else:
        result["value"] = 0
    return result


def _build_heatmap_data(result: ScanResult) -> list[dict]:
    from datetime import datetime
    monthly: dict[str, dict] = {}
    two_years_ago = time.time() - (2 * 365.25 * 86400)
    for f in result.files:
        try:
            dt = datetime.fromtimestamp(f.mtime)
            key = dt.strftime("%Y-%m")
            if key not in monthly:
                monthly[key] = {"month": key, "size": 0, "count": 0, "ghost_count": 0, "ghost_size": 0}
            monthly[key]["size"] += f.size
            monthly[key]["count"] += 1
            if f.size > 50 * 1024 * 1024 and f.mtime < two_years_ago:
                monthly[key]["ghost_count"] += 1
                monthly[key]["ghost_size"] += f.size
        except (OSError, ValueError):
            continue
    return sorted(monthly.values(), key=lambda x: x["month"])


_HTML_HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>fs-scanner Dashboard</title>
"""

_CSS = """<style>
:root{--bg:#0a0a1a;--surface:#12122a;--surface2:#1a1a3a;--border:#2a2a5a;--text:#e8e8f0;--text2:#8888aa;--accent:#6366f1;--accent2:#a78bfa;--green:#34d399;--yellow:#fbbf24;--red:#f87171;--blue:#60a5fa;--radius:12px;--shadow:0 4px 24px rgba(0,0,0,.4)}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Inter',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;line-height:1.5}
.container{max-width:1400px;margin:0 auto;padding:1.5rem}
.header{background:linear-gradient(135deg,var(--surface) 0%,var(--surface2) 100%);border:1px solid var(--border);border-radius:var(--radius);padding:2rem;margin-bottom:1.5rem;box-shadow:var(--shadow)}
.header h1{font-size:1.8rem;font-weight:700;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:.5rem}
.header .subtitle{color:var(--text2);font-size:.9rem}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1rem;margin-top:1.5rem}
.stat-card{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:1rem 1.2rem;text-align:center}
.stat-card .value{font-size:1.6rem;font-weight:700;color:var(--accent2)}
.stat-card .label{font-size:.75rem;color:var(--text2);text-transform:uppercase;letter-spacing:.05em;margin-top:.25rem}
.tabs{display:flex;gap:.5rem;margin-bottom:1.5rem;overflow-x:auto;padding-bottom:.5rem}
.tab{padding:.6rem 1.2rem;border-radius:8px;cursor:pointer;font-size:.85rem;font-weight:500;color:var(--text2);background:var(--surface);border:1px solid transparent;transition:all .2s;white-space:nowrap}
.tab:hover{color:var(--text);border-color:var(--border)}
.tab.active{color:#fff;background:var(--accent);border-color:var(--accent)}
.panel{display:none;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:1.5rem;box-shadow:var(--shadow)}
.panel.active{display:block}
.panel h2{font-size:1.1rem;font-weight:600;margin-bottom:1rem;color:var(--accent2)}
.suggestion-card{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:1rem 1.2rem;margin-bottom:.75rem;display:grid;grid-template-columns:1fr auto auto;gap:1rem;align-items:center}
.suggestion-card .path{font-size:.8rem;color:var(--text2);word-break:break-all}
.suggestion-card .cat{font-weight:600;font-size:.9rem}
.suggestion-card .size{font-size:1.1rem;font-weight:700;color:var(--accent2);white-space:nowrap}
.suggestion-card .reason{font-size:.75rem;color:var(--text2);grid-column:1/-1;border-top:1px solid var(--border);padding-top:.5rem;margin-top:.25rem}
.badge{display:inline-block;padding:.15rem .5rem;border-radius:4px;font-size:.7rem;font-weight:600;text-transform:uppercase}
.badge-safe{background:rgba(52,211,153,.15);color:var(--green)}
.badge-caution{background:rgba(251,191,36,.15);color:var(--yellow)}
.badge-risky{background:rgba(248,113,113,.15);color:var(--red)}
.total-bar{background:linear-gradient(90deg,var(--accent),var(--accent2));border-radius:8px;padding:1rem 1.5rem;margin-bottom:1.5rem;display:flex;justify-content:space-between;align-items:center}
.total-bar .label{color:rgba(255,255,255,.8);font-size:.85rem}
.total-bar .value{font-size:1.4rem;font-weight:700;color:#fff}
table{width:100%;border-collapse:collapse}
th,td{padding:.6rem .8rem;text-align:left;border-bottom:1px solid var(--border);font-size:.85rem}
th{color:var(--text2);font-weight:500;font-size:.75rem;text-transform:uppercase;letter-spacing:.04em;cursor:pointer;user-select:none;position:sticky;top:0;background:var(--surface)}
th:hover{color:var(--accent)}
tr:hover td{background:rgba(99,102,241,.05)}
.filters{display:flex;gap:.75rem;margin-bottom:1rem;flex-wrap:wrap}
.filters input,.filters select{background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:.5rem 1rem;border-radius:6px;font-size:.85rem;outline:none;transition:border-color .2s}
.filters input:focus,.filters select:focus{border-color:var(--accent)}
.filters input{min-width:220px}
#treemap-container svg{width:100%;height:500px;border-radius:8px;overflow:hidden}
#pie-container svg{width:100%;max-width:500px;height:400px;margin:0 auto;display:block}
.breadcrumb{margin-bottom:1rem;font-size:.85rem;color:var(--text2)}
.breadcrumb span{cursor:pointer;color:var(--accent);transition:opacity .2s}
.breadcrumb span:hover{opacity:.7}
.heatmap-wrap{display:flex;flex-wrap:wrap;gap:4px;align-items:flex-end}
.heatmap-cell{border-radius:3px;cursor:pointer;transition:transform .1s}
.heatmap-cell:hover{transform:scale(1.3)}
.tooltip{position:absolute;background:var(--surface2);border:1px solid var(--border);padding:.4rem .7rem;border-radius:6px;font-size:.75rem;pointer-events:none;z-index:1000;box-shadow:var(--shadow)}
.empty-state{text-align:center;padding:3rem;color:var(--text2)}
@media(max-width:768px){.container{padding:1rem}.stats-grid{grid-template-columns:1fr 1fr}.suggestion-card{grid-template-columns:1fr}}
</style>
"""


_HTML_BODY = """
<div class="container">
  <div class="header">
    <h1>fs-scanner</h1>
    <div class="subtitle" id="scan-subtitle"></div>
    <div class="stats-grid" id="stats-grid"></div>
  </div>
  <div class="tabs">
    <div class="tab active" data-panel="suggestions">Suggestions</div>
    <div class="tab" data-panel="treemap">Treemap</div>
    <div class="tab" data-panel="categories">Categories</div>
    <div class="tab" data-panel="files">Top Files</div>
    <div class="tab" data-panel="heatmap">Heatmap</div>
  </div>
  <div class="panel active" id="panel-suggestions">
    <div class="total-bar" id="total-bar"></div>
    <div id="suggestions-list"></div>
  </div>
  <div class="panel" id="panel-treemap">
    <h2>Disk Usage Treemap</h2>
    <div class="breadcrumb" id="treemap-breadcrumb"></div>
    <div id="treemap-container"></div>
  </div>
  <div class="panel" id="panel-categories">
    <h2>Usage by Category</h2>
    <div id="pie-container"></div>
    <table id="cat-table"><thead><tr><th>Category</th><th>Size</th><th>Files</th><th>%</th></tr></thead><tbody></tbody></table>
  </div>
  <div class="panel" id="panel-files">
    <h2>Largest Files</h2>
    <div class="filters">
      <input type="text" id="file-search" placeholder="Search filename...">
      <select id="file-cat-filter"><option value="">All categories</option></select>
    </div>
    <div style="max-height:500px;overflow-y:auto">
      <table id="file-table"><thead><tr><th data-col="path">Path</th><th data-col="size">Size</th><th data-col="category">Category</th><th data-col="mtime">Modified</th></tr></thead><tbody></tbody></table>
    </div>
  </div>
  <div class="panel" id="panel-heatmap">
    <h2>File Modification Heatmap</h2>
    <div class="heatmap-wrap" id="heatmap-container"></div>
    <div id="heatmap-detail" style="margin-top:1.5rem"></div>
  </div>
</div>
<div class="tooltip" id="tooltip" style="display:none"></div>
"""


_DASHBOARD_JS = """<script>
const D=SCAN_DATA,tooltip=document.getElementById('tooltip');
function fmt(b){if(b<1024)return b+' B';if(b<1048576)return(b/1024).toFixed(1)+' KB';if(b<1073741824)return(b/1048576).toFixed(1)+' MB';if(b<1099511627776)return(b/1073741824).toFixed(1)+' GB';return(b/1099511627776).toFixed(1)+' TB'}
function fdate(ts){return new Date(ts*1000).toLocaleDateString('it-IT',{day:'2-digit',month:'short',year:'numeric'})}

// Header
document.getElementById('scan-subtitle').textContent=`Scanned ${D.root} on ${new Date(D.timestamp).toLocaleString('it-IT')}`;
const totalSugg=D.suggestions.reduce((a,s)=>a+s.size,0);
document.getElementById('stats-grid').innerHTML=`
<div class="stat-card"><div class="value">${fmt(D.total_size)}</div><div class="label">Total Scanned</div></div>
<div class="stat-card"><div class="value">${D.total_files.toLocaleString()}</div><div class="label">Files</div></div>
<div class="stat-card"><div class="value">${D.categories.length}</div><div class="label">Categories</div></div>
<div class="stat-card"><div class="value">${fmt(totalSugg)}</div><div class="label">Reclaimable</div></div>`;

// Tabs
document.querySelectorAll('.tab').forEach(t=>{t.addEventListener('click',()=>{
document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));
t.classList.add('active');document.getElementById('panel-'+t.dataset.panel).classList.add('active');
if(t.dataset.panel==='treemap'&&!window._tm)drawTreemap();
if(t.dataset.panel==='categories'&&!window._pie)drawPie();
if(t.dataset.panel==='heatmap'&&!window._hm)drawHeatmap();
})});

// === SUGGESTIONS ===
(function(){
const el=document.getElementById('suggestions-list'),bar=document.getElementById('total-bar');
if(!D.suggestions.length){el.innerHTML='<div class="empty-state">No suggestions. Your disk looks clean!</div>';bar.style.display='none';return}
bar.innerHTML=`<span class="label">Total reclaimable space</span><span class="value">${fmt(totalSugg)}</span>`;
el.innerHTML=D.suggestions.map(s=>{
const bc=s.risk==='safe'?'badge-safe':s.risk==='caution'?'badge-caution':'badge-risky';
const shortPath=s.path.length>60?'...'+s.path.slice(-57):s.path;
return`<div class="suggestion-card"><div><div class="cat">${s.category}</div><div class="path" title="${s.path}">${shortPath}</div></div><div><span class="badge ${bc}">${s.risk}</span></div><div class="size">${fmt(s.size)}</div><div class="reason">${s.reason}</div></div>`
}).join('');
})();

// === TREEMAP ===
function drawTreemap(){
window._tm=true;const container=document.getElementById('treemap-container');
const width=container.clientWidth||900,height=500;container.innerHTML='';
const root=d3.hierarchy(D.tree).sum(d=>d.value||0).sort((a,b)=>b.value-a.value);
const treemap=d3.treemap().size([width,height]).paddingInner(2).paddingOuter(4).round(true);
treemap(root);
const svg=d3.select(container).append('svg').attr('viewBox',`0 0 ${width} ${height}`);
const color=d3.scaleOrdinal(d3.schemeTableau10);
let current=root;const breadcrumb=document.getElementById('treemap-breadcrumb');
function render(node){
current=node;svg.selectAll('*').remove();
const leaves=node.children||[node];
const g=svg.selectAll('g').data(leaves).join('g').attr('transform',d=>`translate(${d.x0},${d.y0})`);
g.append('rect').attr('width',d=>Math.max(0,d.x1-d.x0)).attr('height',d=>Math.max(0,d.y1-d.y0))
.attr('fill',(d,i)=>color(i%10)).attr('opacity',.85).attr('rx',4)
.style('cursor',d=>d.children?'pointer':'default')
.on('click',(e,d)=>{if(d.children){treemap(d);render(d)}})
.on('mouseover',(e,d)=>{tooltip.style.display='block';tooltip.textContent=d.data.name+': '+fmt(d.value)})
.on('mousemove',e=>{tooltip.style.left=(e.pageX+12)+'px';tooltip.style.top=(e.pageY-24)+'px'})
.on('mouseout',()=>{tooltip.style.display='none'});
g.append('text').attr('x',6).attr('y',16).attr('fill','#fff').attr('font-size','11px').attr('font-weight','500')
.text(d=>{const w=d.x1-d.x0;return w>50?d.data.name.slice(0,Math.floor(w/7)):''});
let path=[];let n=node;while(n){path.unshift(n);n=n.parent}
breadcrumb.innerHTML=path.map((p,i)=>i<path.length-1?`<span data-idx="${i}">${p.data.name}</span> / `:p.data.name).join('');
breadcrumb.querySelectorAll('span').forEach(s=>{s.addEventListener('click',()=>{const idx=+s.dataset.idx;treemap(path[idx]);render(path[idx])})});
}
treemap(root);render(root);
}
</script>
<script>
// === PIE CHART ===
function drawPie(){
window._pie=true;const container=document.getElementById('pie-container');
const w=400,h=400,r=Math.min(w,h)/2-30;container.innerHTML='';
const svg=d3.select(container).append('svg').attr('viewBox',`0 0 ${w} ${h}`).append('g').attr('transform',`translate(${w/2},${h/2})`);
const color=d3.scaleOrdinal(d3.schemeTableau10);
const pie=d3.pie().value(d=>d.size).sort(null);
const arc=d3.arc().innerRadius(r*.5).outerRadius(r);
const labelArc=d3.arc().innerRadius(r*.75).outerRadius(r*.75);
const arcs=svg.selectAll('.arc').data(pie(D.categories)).join('g');
arcs.append('path').attr('d',arc).attr('fill',(d,i)=>color(i)).attr('opacity',.9).attr('stroke','var(--bg)').attr('stroke-width',2)
.on('mouseover',(e,d)=>{tooltip.style.display='block';tooltip.textContent=d.data.name+': '+fmt(d.data.size)+' ('+d.data.pct.toFixed(1)+'%)'})
.on('mousemove',e=>{tooltip.style.left=(e.pageX+12)+'px';tooltip.style.top=(e.pageY-24)+'px'})
.on('mouseout',()=>{tooltip.style.display='none'});
arcs.append('text').attr('transform',d=>`translate(${labelArc.centroid(d)})`).attr('text-anchor','middle')
.attr('fill','#fff').attr('font-size','10px').attr('font-weight','600').text(d=>d.data.pct>4?d.data.name:'');
const tbody=document.querySelector('#cat-table tbody');
tbody.innerHTML=D.categories.map(c=>`<tr><td>${c.name}</td><td>${fmt(c.size)}</td><td>${c.count.toLocaleString()}</td><td>${c.pct.toFixed(1)}%</td></tr>`).join('');
}

// === FILE TABLE ===
let sortCol='size',sortAsc=false;
function renderFileTable(){
const tbody=document.querySelector('#file-table tbody');
const search=document.getElementById('file-search').value.toLowerCase();
const catFilter=document.getElementById('file-cat-filter').value;
let filtered=D.files.filter(f=>{
if(search&&!f.path.toLowerCase().includes(search))return false;
if(catFilter&&f.category!==catFilter)return false;return true});
filtered.sort((a,b)=>{let va=a[sortCol],vb=b[sortCol];if(typeof va==='string'){va=va.toLowerCase();vb=vb.toLowerCase()}return sortAsc?(va>vb?1:-1):(va<vb?1:-1)});
tbody.innerHTML=filtered.slice(0,200).map(f=>`<tr><td title="${f.path}">${f.path.length>70?'...'+f.path.slice(-67):f.path}</td><td>${fmt(f.size)}</td><td>${f.category}</td><td>${fdate(f.mtime)}</td></tr>`).join('')}
const cats=[...new Set(D.files.map(f=>f.category))].sort();
const sel=document.getElementById('file-cat-filter');
cats.forEach(c=>{const o=document.createElement('option');o.value=c;o.textContent=c;sel.appendChild(o)});
document.getElementById('file-search').addEventListener('input',renderFileTable);
document.getElementById('file-cat-filter').addEventListener('change',renderFileTable);
document.querySelectorAll('#file-table th').forEach(th=>{th.addEventListener('click',()=>{const col=th.dataset.col;if(!col)return;if(sortCol===col)sortAsc=!sortAsc;else{sortCol=col;sortAsc=false}renderFileTable()})});
renderFileTable();

// === HEATMAP ===
function drawHeatmap(){
window._hm=true;const container=document.getElementById('heatmap-container');
if(!D.heatmap.length){container.innerHTML='<div class="empty-state">No heatmap data available.</div>';return}
const maxSize=Math.max(...D.heatmap.map(h=>h.size));
const colorScale=d3.scaleSequential(d3.interpolateInferno).domain([0,maxSize]);
container.innerHTML=D.heatmap.map(h=>{
const ghost=h.ghost_count>0?' outline:2px solid var(--red);':'';
return`<div style="text-align:center"><div class="heatmap-cell" style="background:${colorScale(h.size)};width:28px;height:28px;${ghost}" data-month="${h.month}" title="${h.month}: ${fmt(h.size)} (${h.count} files)"></div><div style="font-size:8px;color:var(--text2);margin-top:3px">${h.month.slice(2)}</div></div>`}).join('');
if(D.heatmap.some(h=>h.ghost_count>0)){
const totalGhost=D.heatmap.reduce((s,h)=>s+h.ghost_size,0);
container.innerHTML+=`<p style="margin-top:1rem;color:var(--red);font-size:.8rem">Ghost files (>50MB, >2yr old): ${fmt(totalGhost)}</p>`}
container.querySelectorAll('.heatmap-cell').forEach(cell=>{cell.addEventListener('click',()=>{
const m=cell.dataset.month,detail=document.getElementById('heatmap-detail');
const mf=D.files.filter(f=>{const d=new Date(f.mtime*1000);return d.toISOString().slice(0,7)===m}).sort((a,b)=>b.size-a.size).slice(0,15);
detail.innerHTML=`<h2 style="color:var(--accent2)">Files modified in ${m}</h2><table><thead><tr><th>Path</th><th>Size</th></tr></thead><tbody>`+mf.map(f=>`<tr><td>${f.path}</td><td>${fmt(f.size)}</td></tr>`).join('')+'</tbody></table>'})})
}
</script>
"""
