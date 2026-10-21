# -*- coding: utf-8 -*-
"""生成可勾选的岗位清单（HTML + CSV）。"""
import csv
import json
import os

TPL = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
  :root{--bg:#f6f7f9;--card:#fff;--line:#e6e8ec;--txt:#1c2026;--sub:#6b7280;--brand:#1f5eff;}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--txt);font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;}
  .wrap{max-width:1480px;margin:0 auto;padding:24px 20px 120px;}
  h1{font-size:22px;margin:0 0 6px}
  .meta{color:var(--sub);font-size:13px}
  .stats{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:18px 0}
  .stat{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
  .stat .n{font-size:24px;font-weight:650}
  .stat .l{color:var(--sub);font-size:12px}
  .bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;background:var(--card);
       border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin-bottom:14px;position:sticky;top:0;z-index:20}
  .tabs{display:flex;gap:4px;background:#f1f3f6;padding:3px;border-radius:9px}
  .tabs button{border:0;background:transparent;padding:6px 12px;border-radius:7px;cursor:pointer;font-size:13px;color:#4b5563}
  .tabs button.on{background:#fff;color:var(--brand);font-weight:600}
  select,input[type=search]{border:1px solid var(--line);background:#fff;border-radius:8px;padding:7px 10px;font-size:13px;font-family:inherit}
  input[type=search]{min-width:220px}
  table{width:100%;border-collapse:separate;border-spacing:0;background:var(--card);border:1px solid var(--line);border-radius:12px}
  th,td{padding:11px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
  th{background:#fafbfc;font-weight:600;font-size:12.5px;color:#4b5563;white-space:nowrap}
  tr:last-child td{border-bottom:0}
  tbody tr:hover{background:#fbfcfe}
  .ck{width:34px;text-align:center}
  .unit{font-weight:600}
  a{color:var(--brand);text-decoration:none}
  a:hover{text-decoration:underline}
  .tags{display:flex;flex-wrap:wrap;gap:4px;margin-top:5px}
  .tag{font-size:11.5px;padding:1px 7px;border-radius:999px;background:#f1f3f6;color:#4b5563}
  .tag.t1{background:#e8f5ec;color:#0b7a44}
  .tag.t2{background:#eef3ff;color:#1f4fd8}
  .tag.t3{background:#fdf3e3;color:#a25b06}
  .kind,.prov{font-size:12px;color:var(--sub)}
  .sal{font-variant-numeric:tabular-nums;white-space:nowrap}
  .sal.dim{color:var(--sub)}
  .city{white-space:nowrap}
  .jobs{margin:4px 0 0;padding:0;list-style:none;font-size:12.5px;color:#374151}
  .jobs li{margin:2px 0}
  .jobs li span.s{color:var(--sub)}
  .score{display:inline-block;min-width:26px;text-align:center;font-weight:650}
  .note{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-top:16px;color:#4b5563;font-size:13px}
  .note h3{margin:0 0 8px;font-size:13.5px;color:var(--txt)}
  .note ul{margin:0;padding-left:18px}
  .dock{position:fixed;left:0;right:0;bottom:0;background:rgba(255,255,255,.96);border-top:1px solid var(--line);padding:12px 20px;z-index:50}
  .dock .inner{max-width:1480px;margin:0 auto;display:flex;gap:14px;align-items:center;justify-content:space-between}
  .btn{border:1px solid var(--brand);background:var(--brand);color:#fff;border-radius:9px;padding:9px 18px;font-size:13.5px;cursor:pointer;font-family:inherit}
  .btn.ghost{background:#fff;color:var(--brand)}
  .btn:disabled{opacity:.45;cursor:not-allowed}
  .cnt b{font-size:18px;color:var(--brand)}
  @media(max-width:980px){.stats{grid-template-columns:repeat(2,1fr)}}
</style>
</head>
<body>
<div class="wrap">
  <h1>__TITLE__</h1>
  <div class="meta">来源 <b>__SOURCE__</b> ｜ 生成时间 <b>__TIME__</b> ｜ 筛选条件：<b>__FILTERS__</b></div>
  <div class="stats">
    <div class="stat"><div class="n">__S_T1__</div><div class="l">首选（强匹配）</div></div>
    <div class="stat"><div class="n">__S_T2__</div><div class="l">可投（需定制）</div></div>
    <div class="stat"><div class="n">__S_T3__</div><div class="l">冲刺（门槛偏高）</div></div>
    <div class="stat"><div class="n">__S_UNITS__</div><div class="l">在招单位</div></div>
    <div class="stat"><div class="n">__S_JOBS__</div><div class="l">匹配岗位</div></div>
  </div>
  <div class="bar">
    <div class="tabs" id="tabs">
      <button data-t="all" class="on">全部</button>
      <button data-t="tier1">首选</button>
      <button data-t="tier2">可投</button>
      <button data-t="tier3">冲刺</button>
    </div>
    <select id="kind"><option value="">全部单位类型</option></select>
    <select id="city"><option value="">全部城市</option></select>
    <input type="search" id="q" placeholder="搜索单位 / 岗位关键词">
    <span class="meta" id="shown"></span>
  </div>
  <table>
    <thead><tr>
      <th class="ck"><input type="checkbox" id="all"></th>
      <th>单位</th><th>城市</th><th>单位类型</th><th>推荐岗位</th><th>待遇</th><th>在招</th><th>分</th>
    </tr></thead>
    <tbody id="tb"></tbody>
  </table>
  <div class="note">
    <h3>怎么用这份清单</h3>
    <ul>
      <li><b>首选</b>：学科方向直接对口，单位层次与你的成果量级匹配，命中率最高。</li>
      <li><b>可投</b>：方向沾边，需要按岗位调整简历侧重点，别用同一份材料。</li>
      <li><b>冲刺</b>：单位层次或岗位要求偏高，可以投但预期放低。</li>
      <li>勾选后点右下角导出 CSV，即可拿到待投名单。</li>
      <li>「在招」是该单位平台上同时挂出的相关岗位数，数量多说明在集中引才，回复率通常更高。</li>
    </ul>
  </div>
</div>
<div class="dock"><div class="inner">
  <div class="cnt">已选 <b id="n">0</b> 家单位</div>
  <div style="display:flex;gap:10px">
    <button class="btn ghost" id="clear">清空</button>
    <button class="btn" id="exp" disabled>导出勾选清单 CSV</button>
  </div>
</div></div>
<script>
const DATA = __DATA__;
const KEY = "pick_v1";
let tier = "all", picks = new Set(JSON.parse(localStorage.getItem(KEY) || "[]"));
const rows = [];
DATA.tier1.forEach(u => rows.push({...u, tier:"tier1"}));
DATA.tier2.forEach(u => rows.push({...u, tier:"tier2"}));
DATA.tier3.forEach(u => rows.push({...u, tier:"tier3"}));
function uniq(a){return [...new Set(a)].filter(Boolean).sort();}
const kindSel = document.getElementById("kind"), citySel = document.getElementById("city");
uniq(rows.map(r=>r.kind)).forEach(v=>kindSel.add(new Option(v,v)));
uniq(rows.map(r=>r.city)).forEach(v=>citySel.add(new Option(v,v)));
function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}
function render(){
  const q = document.getElementById("q").value.trim();
  const k = kindSel.value, c = citySel.value;
  const list = rows.filter(r=>{
    if(tier!=="all" && r.tier!==tier) return false;
    if(k && r.kind!==k) return false;
    if(c && r.city!==c) return false;
    if(q){
      const blob=[r.company, r.city, ...r.top_jobs.map(j=>j.title)].join(" ");
      if(!blob.includes(q)) return false;
    }
    return true;
  });
  document.getElementById("tb").innerHTML = list.map(r=>{
    const tcls = r.tier==="tier1"?"t1":r.tier==="tier2"?"t2":"t3";
    const jobs = r.top_jobs.map(j=>`<li><a href="${j.url}" target="_blank">${esc(j.title)}</a> <span class="s">· ${esc(j.type)} · ${esc(j.salary)}</span></li>`).join("");
    return `<tr>
      <td class="ck"><input type="checkbox" class="pick" data-id="${r.company_id}" ${picks.has(String(r.company_id))?"checked":""}></td>
      <td><div class="unit"><a href="${r.unit_url}" target="_blank">${esc(r.company)}</a></div>
          <div class="tags"><span class="tag ${tcls}">${r.tier==="tier1"?"首选":r.tier==="tier2"?"可投":"冲刺"}</span>${r.types.slice(0,3).map(t=>`<span class="tag">${esc(t)}</span>`).join("")}</div></td>
      <td class="city">${esc(r.city)}</td>
      <td class="kind">${esc(r.kind)}</td>
      <td><ul class="jobs">${jobs}</ul></td>
      <td class="sal ${r.salary==="面议"?"dim":""}">${esc(r.salary)}</td>
      <td class="sal">${r.job_count}</td>
      <td><span class="score">${r.max_score}</span></td>
    </tr>`;
  }).join("");
  document.getElementById("shown").textContent = `共 ${list.length} 家`;
  document.querySelectorAll(".pick").forEach(el=>el.addEventListener("change",e=>{
    const id=e.target.dataset.id;
    e.target.checked ? picks.add(id) : picks.delete(id);
    localStorage.setItem(KEY, JSON.stringify([...picks]));
    sync();
  }));
  sync();
}
function sync(){ document.getElementById("n").textContent = picks.size;
  document.getElementById("exp").disabled = picks.size===0; }
document.getElementById("tabs").addEventListener("click",e=>{
  const b=e.target.closest("button"); if(!b) return;
  tier=b.dataset.t; [...e.currentTarget.children].forEach(x=>x.classList.toggle("on",x===b)); render();
});
[kindSel,citySel].forEach(s=>s.addEventListener("change",render));
document.getElementById("q").addEventListener("input",render);
document.getElementById("all").addEventListener("change",e=>{
  document.querySelectorAll(".pick").forEach(el=>{ el.checked=e.target.checked;
    e.target.checked ? picks.add(el.dataset.id) : picks.delete(el.dataset.id); });
  localStorage.setItem(KEY, JSON.stringify([...picks])); sync();
});
document.getElementById("clear").addEventListener("click",()=>{picks.clear();localStorage.setItem(KEY,"[]");render();});
document.getElementById("exp").addEventListener("click",()=>{
  const sel = rows.filter(r=>picks.has(String(r.company_id)));
  const lines = [["单位","城市","单位类型","在招岗位数","待遇","代表岗位","岗位链接","单位链接"].join(",")];
  sel.forEach(r=>{ const j=r.top_jobs[0]||{};
    lines.push([r.company,r.city,r.kind,r.job_count,r.salary,j.title||"",j.url||"",r.unit_url]
      .map(v=>`"${String(v).replace(/"/g,'""')}"`).join(",")); });
  const a=document.createElement("a");
  a.href=URL.createObjectURL(new Blob(["\ufeff"+lines.join("\n")],{type:"text/csv;charset=utf-8"}));
  a.download="勾选投递清单.csv"; a.click();
});
render();
</script>
</body>
</html>
"""


def render(shortlist, out_html, out_csv, filters_text=""):
    slim = {}
    for k in ("tier1", "tier2", "tier3"):
        arr = []
        for u in shortlist[k]:
            arr.append({
                "company": u["company"], "company_id": u["company_id"], "city": u["city"],
                "kind": u["kind"], "job_count": u["job_count"], "max_score": u["max_score"],
                "types": u["types"], "salary": u["salary"], "unit_url": u["unit_url"],
                "top_jobs": [{"title": j["title"], "salary": j["salary_str"],
                              "type": j["_type"], "url": j["_url"]} for j in u["top_jobs"]],
            })
        slim[k] = arr

    html = TPL
    html = html.replace("__DATA__", json.dumps(slim, ensure_ascii=False))
    html = html.replace("__TITLE__", shortlist.get("title", "岗位投递清单"))
    html = html.replace("__SOURCE__", shortlist.get("source", ""))
    html = html.replace("__TIME__", shortlist.get("collected_at", ""))
    html = html.replace("__FILTERS__", filters_text)
    st = shortlist["stats"]
    for k, v in (("__S_T1__", st["tier1"]), ("__S_T2__", st["tier2"]), ("__S_T3__", st["tier3"]),
                 ("__S_UNITS__", st["units"]), ("__S_JOBS__", st["matched_positions"])):
        html = html.replace(k, str(v))
    os.makedirs(os.path.dirname(out_html), exist_ok=True)
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)

    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["梯队", "单位", "城市", "单位类型", "在招岗位数", "待遇", "代表岗位", "岗位链接", "单位链接"])
        for k, label in (("tier1", "首选"), ("tier2", "可投"), ("tier3", "冲刺")):
            for u in shortlist[k]:
                j = u["top_jobs"][0]
                w.writerow([label, u["company"], u["city"], u["kind"], u["job_count"],
                            u["salary"], j["title"], j["_url"], u["unit_url"]])
    return out_html, out_csv
