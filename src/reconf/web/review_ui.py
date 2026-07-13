"""리뷰 승인 화면 (M6, 설계 §6.5·§12.1).

`/api/review/queue`를 불러와 표로 보여주고, 승인/반려를 선택해
`/api/review/decisions`로 제출하는 자체 완결형 HTML(외부 의존성 없음).
"""

from __future__ import annotations

REVIEW_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>검수 승인 — Confluence AI 재구성</title>
<style>
  :root{--bg:#f4f5f7;--panel:#fff;--ink:#172b4d;--sub:#5e6c84;--line:#dfe1e6;
    --brand:#0052cc;--brand-soft:#deebff;--ok:#00875a;--ok-soft:#e3fcef;--warn:#974f0c;--warn-soft:#fff0b3;--chip:#ebecf0;}
  @media (prefers-color-scheme:dark){:root{--bg:#1b1f27;--panel:#22272e;--ink:#c7d1de;--sub:#8b98a9;
    --line:#333b45;--brand:#579dff;--brand-soft:#0b2444;--ok:#4bce97;--ok-soft:#123326;--warn:#f5cd47;--warn-soft:#3a2f0b;--chip:#2c333c;}}
  *{box-sizing:border-box} body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Malgun Gothic",sans-serif;
    background:var(--bg);color:var(--ink);font-size:14px}
  header{background:var(--panel);border-bottom:1px solid var(--line);padding:12px 20px;display:flex;align-items:center;gap:12px;position:sticky;top:0;z-index:5}
  .logo{width:26px;height:26px;border-radius:6px;background:var(--brand);color:#fff;display:grid;place-items:center;font-weight:800}
  header h1{font-size:16px;margin:0}
  header .sub{color:var(--sub);font-size:12px}
  .bar{margin-left:auto;display:flex;gap:8px}
  .btn{border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:6px;padding:8px 14px;cursor:pointer;font-size:13px}
  .btn.primary{background:var(--brand);border-color:var(--brand);color:#fff;font-weight:600}
  .wrap{max-width:1080px;margin:18px auto;padding:0 20px}
  .stat{color:var(--sub);font-size:13px;margin-bottom:10px}
  table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}
  th,td{padding:10px 12px;border-bottom:1px solid var(--line);text-align:left;font-size:13px;vertical-align:middle}
  th{background:var(--bg);color:var(--sub);white-space:nowrap}
  tr:hover td{background:var(--brand-soft)}
  .lab{display:inline-block;background:var(--brand-soft);color:var(--brand);border-radius:12px;padding:1px 8px;font-size:11px;margin:1px}
  .badge{padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700}
  .dup{background:var(--warn-soft);color:var(--warn)} .can{background:var(--ok-soft);color:var(--ok)}
  .conf{font-variant-numeric:tabular-nums;font-weight:700}
  .lo{color:#bf2600}.mid{color:var(--warn)}.hi{color:var(--ok)}
  .seg{display:inline-flex;border:1px solid var(--line);border-radius:6px;overflow:hidden}
  .seg button{border:none;background:var(--panel);color:var(--sub);padding:5px 10px;cursor:pointer;font-size:12px}
  .seg button.on-ok{background:var(--ok);color:#fff} .seg button.on-no{background:#bf2600;color:#fff}
  #msg{margin:10px 0;font-size:13px}
  .empty{padding:40px;text-align:center;color:var(--sub)}
</style>
</head>
<body>
<header>
  <div class="logo">R</div>
  <div><h1>검수 승인 (Review)</h1><div class="sub">저신뢰·중복 후보 우선 · 승인된 문서만 업로드 대상</div></div>
  <div class="bar">
    <button class="btn" onclick="load()">새로고침</button>
    <button class="btn primary" onclick="submitAll()">제출 (Submit)</button>
  </div>
</header>
<div class="wrap">
  <div class="stat" id="stat">불러오는 중…</div>
  <div id="msg"></div>
  <table>
    <thead><tr><th>문서</th><th>업무/연도</th><th>라벨</th><th>신뢰도</th><th>구분</th><th>결정</th></tr></thead>
    <tbody id="rows"></tbody>
  </table>
</div>
<script>
let items = [];
const decisions = {};   // page_id -> 'approved' | 'rejected'

function confClass(v){ return v < 0.5 ? 'lo' : (v < 0.7 ? 'mid' : 'hi'); }
function esc(s){ return (s??'').toString().replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

async function load(){
  document.getElementById('msg').textContent = '';
  const r = await fetch('/api/review/queue');
  items = await r.json();
  render();
}

function render(){
  const tb = document.getElementById('rows');
  document.getElementById('stat').textContent =
    `총 ${items.length}건 · 중복후보 ${items.filter(i=>i.role==='duplicate').length} · 저신뢰(<0.7) ${items.filter(i=>i.min_confidence<0.7).length}`;
  if(!items.length){ tb.innerHTML = '<tr><td colspan="6"><div class="empty">검수할 항목이 없습니다. cluster·analyze 후 큐가 생성됩니다.</div></td></tr>'; return; }
  tb.innerHTML = items.map(it => {
    const labels = (it.labels||[]).map(l=>`<span class="lab">${esc(l)}</span>`).join(' ');
    const role = it.role==='duplicate'
      ? `<span class="badge dup">중복후보${it.duplicate_of?' ↔ '+esc(it.duplicate_of):''}</span>`
      : '<span class="badge can">정본</span>';
    const c = it.min_confidence;
    return `<tr>
      <td><b>${esc(it.title)}</b><div class="sub" style="color:var(--sub);font-size:11px">${esc(it.source_page_id)}</div></td>
      <td>${esc(it.business||'미분류')} / ${it.year??''}</td>
      <td>${labels}</td>
      <td class="conf ${confClass(c)}">${c.toFixed(2)}</td>
      <td>${role}</td>
      <td><span class="seg" data-id="${esc(it.source_page_id)}">
        <button onclick="decide('${esc(it.source_page_id)}','approved',this)">승인</button>
        <button onclick="decide('${esc(it.source_page_id)}','rejected',this)">반려</button>
      </span></td>
    </tr>`;
  }).join('');
}

function decide(id, status, btn){
  decisions[id] = status;
  const seg = btn.parentElement;
  seg.querySelectorAll('button').forEach(b=>b.className='');
  btn.className = status==='approved' ? 'on-ok' : 'on-no';
}

async function submitAll(){
  const payload = Object.entries(decisions).map(([source_page_id, status]) => ({source_page_id, status, reviewer:'web'}));
  if(!payload.length){ document.getElementById('msg').textContent='승인/반려를 먼저 선택하세요.'; return; }
  const r = await fetch('/api/review/decisions', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  const j = await r.json();
  document.getElementById('msg').innerHTML = `<span style="color:var(--ok)">반영됨: ${j.applied}건 (승인 ${j.approved}) — 이제 upload 단계에서 승인 문서만 업로드됩니다.</span>`;
}

load();
</script>
</body>
</html>
"""
