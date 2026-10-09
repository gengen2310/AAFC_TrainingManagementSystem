// Main TMS module: dashboards and reports -- drill-down, chart helpers, the
// Training Dashboard loader, facilitator statistics, Wing/National command
// dashboards and Audit.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// ═══════════════════════════════════════════════════════════
//  DRILL-DOWN
// ═══════════════════════════════════════════════════════════
function drillStatus(st){
  const sess=allSess().filter(s=>s.status===st);
  const stLbls={delivered:'Delivered',planned:'Planned',not_delivered:'Not Delivered',cancelled:'Cancelled',rescheduled:'↺ Rescheduled'};
  showDrill('dash-drill','dash-drill-title','dash-drill-body',stLbls[st]||st,sess);
}
function showDrill(panelId,titleId,bodyId,title,sess){
  document.getElementById(titleId).textContent=title+' ('+sess.length+')';
  document.getElementById(bodyId).innerHTML=sess.length?sess.map(s=>`<tr>
    <td>${fmtD(s.date,{day:'numeric',month:'short'})}</td>
    <td style="color:var(--muted)">S${s.si+1}</td>
    <td>${phBadge(s.phase)}</td>
    <td style="font-weight:700;font-size:var(--fs-sm)">${esc(s.exp||'—')}</td>
    <td style="font-size:var(--fs-xs)">${esc(s.facName||'—')}</td>
    <td style="font-size:var(--fs-xs)">${esc(s.room||'—')}</td>
    <td>${stBadge(s.status)}</td>
    <td class="no-print">${canWriteSquadron()?`<button class="btn btn-xs btn-sky" onclick="quickEdit('${s.date}',${s.si})">Edit</button>`:''}</td>
  </tr>`).join(''):`<tr><td colspan="8" style="text-align:center;color:var(--muted);padding:16px">No sessions</td></tr>`;
  const p=document.getElementById(panelId);p.classList.add('show');p.scrollIntoView({behavior:'smooth',block:'nearest'});
}
function hideDrill(id){document.getElementById(id).classList.remove('show');}
function drillPhaseDash(ph){
  const sess=allSess().filter(s=>s.phase===ph);
  showDrill('dash-drill','dash-drill-title','dash-drill-body',(PH_S[ph]||ph)+' — Sessions',sess);
}

// ═══════════════════════════════════════════════════════════
//  DASHBOARD CHART HELPERS
// ═══════════════════════════════════════════════════════════
function _dEmptyChart(msg){return `<div class="empty" style="padding:16px 12px"><div class="es">${esc(msg)}</div></div>`;}

function _dSetInsight(id,text){const el=document.getElementById(id);if(!el)return;if(text){el.textContent=text;el.style.display='';}else el.style.display='none';}

function _dSetExp(id,text){const el=document.getElementById(id);if(el&&text)el.textContent=text;}

// Horizontal bar chart — handles multiple value-key conventions from the API
function _chartHBar(chart){
  const rows=chart.data||[];
  if(!rows.length)return _dEmptyChart(chart.empty_state||'No data available for this chart.');
  const r0=rows[0];
  const valKey=chart.value_key||(r0.readiness_pct!==undefined?'readiness_pct':r0.delivered!==undefined?'delivered':r0.count!==undefined?'count':r0.value!==undefined?'value':'count');
  const maxV=Math.max(...rows.map(r=>+(r[valKey])||0),1);
  const colorFor=r=>{
    if(r.color)return r.color;
    if(r.readiness_pct!==undefined){const p=r.readiness_pct;return p>=80?'var(--ok)':p>=60?'var(--warn)':'var(--red)';}
    if(r.risk==='ok')return 'var(--ok)';if(r.risk==='warn')return 'var(--warn)';if(r.risk==='critical')return 'var(--red)';
    return 'var(--royal)';
  };
  const lblFor=r=>{
    if(r.readiness_pct!==undefined)return r.readiness_pct+'%';
    if(r.delivered!==undefined&&r.total!==undefined)return r.delivered+' / '+r.total;
    return String(r[valKey]!==undefined?r[valKey]:'');
  };
  return rows.map(r=>{
    const v=+(r[valKey])||0;const w=Math.round(v/maxV*100);const lbl=String(r.label||r.name||'—').substring(0,32);
    const drill=chart.drill_down&&r.drill_id?`onclick="drillDashChart('${esc(chart.chart_id)}','${esc(r.drill_id)}')" style="cursor:pointer"`:'';
    // A data-quality gap (missing phase/reason — see _curriculum_backlog/
    // _cancellation_reasons) is never a real ranked category: shown distinctly
    // (muted dashed bar, "ⓘ" prefix), not styled like a genuine cause.
    const isGap=!!r.data_quality_gap;
    return `<div class="ph-row" style="margin-bottom:5px" role="img" aria-label="${esc(lbl)}: ${lblFor(r)}" ${drill}>
      <div class="ph-name" style="min-width:110px;font-size:var(--fs-xs);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;${isGap?'font-style:italic;color:var(--muted)':''}" title="${esc(r.label||r.name||'')}">${isGap?'ⓘ ':''}${esc(_dLabel(lbl))}</div>
      <div class="ph-bar" style="flex:1"><div class="pbar" style="${isGap?'border:1px dashed var(--muted)':''}"><div style="height:100%;width:${w}%;background:${isGap?'var(--muted)':colorFor(r)};border-radius:3px;transition:width .3s" title="${lblFor(r)}"></div></div></div>
      <div class="ph-cnt" style="min-width:52px;text-align:right;font-size:var(--fs-xs);color:var(--muted)">${lblFor(r)}</div>
    </div>`;
  }).join('');
}

// CLASS-07: Training Class curriculum progress — stage aggregate with per-class breakdown.
// data rows: {stage, stage_id, class_count, coverage_pct, delivered, total, classes:[{display_name,delivered,total,coverage_pct}]}
// Classes whose coverage_pct is ≥15pp below the stage aggregate are flagged NEEDS ATTENTION.
// E2: one table over the training classes, merging curriculum progress with
// expected size. Previously two cards rendered the same 21 rows one after the
// other, 2,373px each, so comparing a class's progress against its size meant
// scrolling between them. Keyed on stage + class name, which is what both
// payloads are grouped by.
function _chartClassTable(progressChart, enrollmentChart){
  const pRows=(progressChart&&progressChart.data)||[];
  const eRows=(enrollmentChart&&enrollmentChart.data)||[];
  if(!pRows.length&&!eRows.length){
    return _dEmptyChart('No Training Classes configured for this squadron and year.');
  }
  // expected_count by "stage||class"
  const counts={};
  eRows.forEach(function(r){
    (r.classes||[]).forEach(function(c){ counts[(r.stage||'')+'||'+(c.display_name||'')]=c.expected_count; });
  });
  const stageTotals={};
  eRows.forEach(function(r){ stageTotals[r.stage||'']=r.total_expected; });

  const pct=function(v){return v==null?'\u2014':Math.round(v)+'%';};
  // col() paints the progress BAR — non-text, so 3:1 applies and --warn's
  // 3.35:1 on white is fine there.
  const col=function(v){return v==null?'var(--muted)':v>=80?'var(--ok)':v>=60?'var(--warn)':'var(--red)';};
  // colText() paints the percentage FIGURE, which is text and needs 4.5:1.
  // --warn is 3.35:1 on white and fails; --warn-text is 6.92:1. The token pair
  // already existed for exactly this reason ("DES-H04: --warn fails 3.1:1;
  // --warn-text passes"), but this inline style used the bar colour, and an
  // inline style is invisible to a stylesheet scan. Found by measuring the
  // rendered page on staging. --ok 5.02:1, --red 4.64:1 and --muted 5.56:1 all
  // pass as text on white and are unchanged.
  const colText=function(v){return v==null?'var(--muted)':v>=80?'var(--ok)':v>=60?'var(--warn-text)':'var(--red)';};

  let body='';
  const source = pRows.length?pRows:eRows;
  source.forEach(function(row){
    const stage=row.stage||'No stage assigned';
    const agg=row.coverage_pct!=null?row.coverage_pct:null;
    const total=stageTotals[stage];
    body+='<tr class="cls-stage-row">'
      + '<th scope="rowgroup">'+esc(stage)+'</th>'
      + '<td class="cls-num">'+(total!=null?esc(String(total)):'\u2014')+'</td>'
      + '<td class="cls-prog"><div class="pbar"><div style="height:100%;width:'+(agg!=null?Math.round(agg):0)+'%;background:'+col(agg)+';border-radius:3px"></div></div></td>'
      + '<td class="cls-num" style="color:'+colText(agg)+'">'+pct(agg)+'</td>'
      + '<td></td></tr>';
    (row.classes||[]).forEach(function(cls){
      const nm=cls.display_name||'';
      const num=cls.class_number!=null?'C'+String(cls.class_number).padStart(2,'0')+' · ':'';
      const v=cls.coverage_pct;
      const n=counts[stage+'||'+nm];
      const behind=agg!=null&&v!=null&&v<=agg-15;
      body+='<tr>'
        + '<td class="cls-name"><span class="cls-num-badge">'+esc(num)+'</span>'+esc(nm)+'</td>'
        + '<td class="cls-num">'+(n!=null?esc(String(n)):'\u2014')+'</td>'
        + '<td class="cls-prog"><div class="pbar"><div style="height:100%;width:'+(v!=null?Math.round(v):0)+'%;background:'+col(v)+';border-radius:3px"></div></div></td>'
        + '<td class="cls-num" style="color:'+colText(v)+'">'+pct(v)+'</td>'
        + '<td>'+(behind?'<span class="cls-flag">Needs attention</span>':'')+'</td>'
        + '</tr>';
    });
  });
  return '<div class="tw"><table class="data-table cls-table">'
    + '<thead><tr><th scope="col">Training class</th><th scope="col" class="cls-num">Cadets</th>'
    + '<th scope="col" colspan="2">Curriculum progress</th><th scope="col"><span class="sr-only">Status</span></th></tr></thead>'
    + '<tbody>'+body+'</tbody></table></div>';
}

// Stacked vertical bar — chart.data rows have per-series keys; chart.series=[{key,label,color}]
function _chartStackedBar(chart){
  const rows=chart.data||[];const series=chart.series||[];
  if(!rows.length)return _dEmptyChart(chart.empty_state||'No data available for this chart.');
  const totals=rows.map(r=>series.reduce((s,se)=>s+(+(r[se.key])||0),0));
  const maxV=Math.max(...totals,1);const BAR_H=80;
  let html=`<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px">`+
    series.map(s=>`<span style="display:flex;align-items:center;gap:4px;font-size:var(--fs-2xs)"><span style="display:inline-block;width:10px;height:10px;background:${s.color||'var(--royal)'};border-radius:2px"></span>${esc(s.label)}</span>`).join('')+`</div>`;
  html+=`<div style="overflow-x:auto"><div style="display:flex;align-items:flex-end;gap:3px;min-width:${Math.max(rows.length*44,280)}px;height:${BAR_H+28}px">`;
  rows.forEach((row,ri)=>{
    const total=totals[ri];const hPx=Math.round(total/maxV*BAR_H);
    html+=`<div style="flex:1;display:flex;flex-direction:column;align-items:center;min-width:32px">
      <div style="width:100%;max-width:36px;height:${hPx}px;display:flex;flex-direction:column-reverse;border-radius:3px 3px 0 0;overflow:hidden">
        ${series.map(se=>{const v=+(row[se.key])||0;return v?`<div style="flex:${v};width:100%;background:${se.color||'var(--royal)'}" title="${esc(se.label)}: ${v}"></div>`:''}).join('')}
      </div>
      <div style="font-size:var(--fs-3xs);color:var(--muted);margin-top:3px;text-align:center;writing-mode:vertical-rl;transform:rotate(180deg);height:22px;overflow:hidden;white-space:nowrap" title="${esc(row.label||'')}">${esc((row.label||'').substring(0,8))}</div>
    </div>`;
  });
  html+=`</div></div>`;return html;
}

// Stacked horizontal bar — for curriculum progress by phase
function _chartStackedBarH(chart){
  const rows=chart.data||[];
  const series=chart.series||[{key:'delivered',label:'Delivered',color:'#2e7d32'},{key:'planned',label:'Planned',color:'#51b0e3'},{key:'not_delivered',label:'Not Delivered',color:'#78909c'},{key:'cancelled',label:'Cancelled',color:'#e51937'}];
  if(!rows.length)return _dEmptyChart(chart.empty_state||'No curriculum data yet. Add curriculum items and schedule sessions to see progress.');
  const maxV=Math.max(...rows.map(r=>series.reduce((a,s)=>a+(+(r[s.key])||0),0)),1);
  let html=`<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px">`+
    series.map(s=>`<span style="display:flex;align-items:center;gap:4px;font-size:var(--fs-2xs)"><span style="display:inline-block;width:10px;height:10px;background:${s.color};border-radius:2px"></span>${esc(s.label)}</span>`).join('')+`</div>`;
  rows.forEach(row=>{
    const total=series.reduce((a,s)=>a+(+(row[s.key])||0),0);
    const name=row.phase?(PH_S[row.phase]||row.phase):(row.element||row.label||'—');
    const pctDel=total?Math.round((+(row.delivered)||0)/total*100):0;
    html+=`<div class="ph-row" style="margin-bottom:6px" role="img" aria-label="${esc(name)}: ${pctDel}% delivered">
      <div class="ph-name" style="min-width:84px;font-size:var(--fs-2xs)">${esc(_dLabel(name).substring(0,14))}</div>
      <div class="ph-bar" style="flex:1">
        <div style="display:flex;height:14px;border-radius:3px;overflow:hidden;background:var(--bg)">
          ${series.map(s=>{const v=+(row[s.key])||0;return v?`<div style="flex:${v};background:${s.color};height:100%" title="${esc(s.label)}: ${v}"></div>`:''}).join('')}
          ${total<maxV?`<div style="flex:${maxV-total};height:100%"></div>`:''}
        </div>
      </div>
      <div class="ph-cnt" style="min-width:44px;text-align:right;font-size:var(--fs-2xs);color:var(--muted)">${total||0}</div>
    </div>`;
  });
  return html;
}

// SVG line chart — chart.data=[{label,reliability_pct}], chart.thresholds={green,amber}
function _chartLine(chart){
  const rows=chart.data||[];if(!rows.length)return _dEmptyChart(chart.empty_state||'No trend data');
  const W=560,H=120,PT=10,PR=8,PB=32,PL=28;const IW=W-PL-PR;const IH=H-PT-PB;
  const th=chart.thresholds||{};const tg=th.green||80;const ta=th.amber||60;
  const vals=rows.map(r=>r.reliability_pct!=null?+r.reliability_pct:null);
  const defined=vals.filter(v=>v!==null);
  const minV=defined.length?Math.max(0,Math.min(...defined)-10):0;
  const xOf=i=>PL+(i/Math.max(rows.length-1,1))*IW;
  const yOf=v=>PT+(1-(v-minV)/(100-minV))*IH;
  const pts=rows.map((r,i)=>({x:xOf(i),y:vals[i]!=null?yOf(vals[i]):null}));
  let path='';pts.forEach((p,i)=>{if(p.y==null)return;const prev=pts[i-1];path+=(path===''||!prev||prev.y==null?`M${p.x.toFixed(1)},${p.y.toFixed(1)}`:`L${p.x.toFixed(1)},${p.y.toFixed(1)}`);});
  const yg=Math.max(PT,Math.min(PT+IH,yOf(tg))).toFixed(1);const ya=Math.max(PT,Math.min(PT+IH,yOf(ta))).toFixed(1);
  const step=Math.ceil(rows.length/8);
  return `<div style="overflow-x:auto"><svg viewBox="0 0 ${W} ${H}" style="width:100%;max-width:${W}px;height:${H}px;font-family:inherit" role="img" aria-label="Delivery trend chart">
    <title>Delivery Reliability</title>
    <rect x="${PL}" y="${PT}" width="${IW}" height="${(+yg-PT).toFixed(1)}" fill="#e8f5e9" opacity=".4"/>
    <rect x="${PL}" y="${yg}" width="${IW}" height="${(+ya-+yg).toFixed(1)}" fill="#fff8e1" opacity=".4"/>
    <rect x="${PL}" y="${ya}" width="${IW}" height="${(PT+IH-+ya).toFixed(1)}" fill="#fce4e4" opacity=".4"/>
    <line x1="${PL}" y1="${yg}" x2="${PL+IW}" y2="${yg}" stroke="#2e7d32" stroke-width="1" stroke-dasharray="3,3" opacity=".7"/>
    <line x1="${PL}" y1="${ya}" x2="${PL+IW}" y2="${ya}" stroke="#f57f17" stroke-width="1" stroke-dasharray="3,3" opacity=".7"/>
    <text x="${PL+IW-2}" y="${+yg-2}" font-size="7" fill="#2e7d32" text-anchor="end">${tg}%</text>
    <text x="${PL+IW-2}" y="${+ya-2}" font-size="7" fill="#f57f17" text-anchor="end">${ta}%</text>
    ${[0,20,40,60,80,100].filter(v=>v>=minV).map(v=>`<text x="${PL-3}" y="${(yOf(v)+3).toFixed(1)}" font-size="7" fill="#5c6a76" text-anchor="end">${v}</text><line x1="${PL-2}" y1="${yOf(v).toFixed(1)}" x2="${PL+IW}" y2="${yOf(v).toFixed(1)}" stroke="#d1dce8" stroke-width=".5"/>`).join('')}
    ${path?`<path d="${path}" fill="none" stroke="var(--royal)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`:''}
    ${pts.map((p,i)=>p.y!=null?(rows[i].is_anomaly?`<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="5" fill="${vals[i]>=tg?'#2e7d32':vals[i]>=ta?'#f57f17':'#e51937'}" stroke="#f57f17" stroke-width="2.5"><title>${esc(rows[i].label||'')}: ${vals[i]}% ⚠ anomaly — delivery significantly below average</title></circle>`:`<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="3" fill="${vals[i]>=tg?'#2e7d32':vals[i]>=ta?'#f57f17':'#e51937'}" stroke="white" stroke-width="1.5"><title>${esc(rows[i].label||'')}: ${vals[i]}%</title></circle>`):'').join('')}
    ${rows.filter((_,i)=>i%step===0||i===rows.length-1).map(r=>{const i=rows.indexOf(r);return `<text x="${xOf(i).toFixed(1)}" y="${H-4}" font-size="7" fill="#5c6a76" text-anchor="middle">${esc(r.label||'')}</text>`;}).join('')}
    <line x1="${PL}" y1="${PT}" x2="${PL}" y2="${PT+IH}" stroke="#d1dce8"/>
    <line x1="${PL}" y1="${PT+IH}" x2="${PL+IW}" y2="${PT+IH}" stroke="#d1dce8"/>
  </svg></div>`;
}

// Donut chart — chart.data=[{status,label,count,color}]
function _chartDonut(chart){
  const rows=chart.data||[];if(!rows.length)return _dEmptyChart(chart.empty_state||'No session data yet. Schedule sessions and record outcomes to see this chart.');
  const total=rows.reduce((s,r)=>s+(+(r.count)||0),0);
  if(!total)return _dEmptyChart(chart.empty_state||'No sessions recorded yet. Start recording session outcomes to see this chart.');
  const R=32;const circ=2*Math.PI*R;
  const ST_COL={delivered:'#2e7d32',delivered_with_issue:'#558b2f',not_delivered:'#78909c',cancelled:'#e51937',rescheduled:'#f57f17',planned:'#51b0e3'};
  const clr=r=>r.color||ST_COL[r.status]||'var(--muted)';
  let offset=0;
  const arcs=rows.filter(r=>+(r.count)>0).map(r=>{const cnt=+(r.count);const dash=cnt/total*circ;const arc={offset,dash,gap:circ-dash,...r};offset+=dash;return arc;});
  const conicArgs=arcs.map(a=>`${clr(a)} ${(a.offset/circ*100).toFixed(1)}% ${((a.offset+a.dash)/circ*100).toFixed(1)}%`).join(',');
  const legend=rows.filter(r=>+(r.count)>0).map(r=>{const pct=Math.round(+(r.count)/total*100);return `<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px"><span style="display:inline-block;width:10px;height:10px;background:${clr(r)};border-radius:50%;flex-shrink:0"></span><span style="font-size:var(--fs-xs);color:var(--text)">${esc(r.label||r.status||'—')}</span><span style="font-size:var(--fs-xs);color:var(--muted);margin-left:auto">${r.count} <span style="font-size:var(--fs-3xs)">(${pct}%)</span></span></div>`;}).join('');
  return `<div class="readiness-donut">
    <div class="rdp-ring" style="background:conic-gradient(${conicArgs})" role="img" aria-label="Session outcomes">
      <div class="rdp-inner" style="width:60px;height:60px;font-size:var(--fs-md);color:var(--dark)">${total}</div>
    </div>
    <div style="flex:1">${legend}</div>
  </div>`;
}

// Tonight readiness card — chart_type=readiness_card
function _renderTonightReadiness(chart){
  const d=chart.data||{};
  if(!d.date)return `<div class="card">${_dEmptyChart(chart.empty_state||'No parade night scheduled tonight or this week')}</div>`;
  // A parade night that exists but has zero sessions is "not_planned" — never a
  // misleading 100%/"ready" donut derived from overall_pct (a legacy projection
  // that reads 100 for zero sessions, kept only for older report consumers).
  if(d.planning_status==='not_planned'||!d.sessions_total){
    return `<div class="card card-quiet">
      <h2 class="ctitle">Tonight — <span style="font-weight:400">${fmtD(d.date,{weekday:'long',day:'numeric',month:'long'})}</span></h2>
      <div style="font-size:var(--fs-base);font-weight:700;color:var(--muted)">Not planned</div>
      <div style="font-size:var(--fs-xs);color:var(--muted);margin-top:4px">No sessions scheduled for this parade night yet.</div>
    </div>`;
  }
  const pct=d.overall_pct||0;const rdC=pct>=80?'var(--ok)':pct>=60?'var(--warn)':'var(--red)';
  const tonightCardCls=pct>=80?'card-ok':pct>=60?'card-warn':'card-alert'; /* DES-M05 semantic border */
  const conic=`conic-gradient(${rdC} ${pct}%, var(--border) 0)`;
  const unstaffedCount=(d.sessions||[]).filter(s=>!s.facilitator).length;
  const sessHtml=(d.sessions||[]).map((s,i)=>`<div class="sched-lane">
    <span style="font-size:var(--fs-2xs);color:var(--muted);min-width:48px">Sess ${i+1}</span>
    <span style="font-size:var(--fs-xs);font-weight:700;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(s.title||'No curriculum item')}</span>
    <span style="font-size:var(--fs-2xs);color:${s.facilitator?'var(--muted)':'var(--red)'}">${esc(s.facilitator||'No facilitator assigned')}</span>
  </div>`).join('');
  // HELP-04: per-item readiness checklist — each preparation category shown
  // as ✓ / ! / ✗ so users can see exactly what is and is not ready, rather
  // than inferring it from a blended percentage.
  const sessTotal=d.sessions_total||0;
  const facFill=d.fac_filled||0;const roomFill=d.room_filled||0;
  function _rdItem(label,filled,total){
    if(!total)return '';
    const ok=filled>=total,none=filled===0;
    const cls=ok?'b-ok':none?'b-red':'b-amber';
    const sym=ok?'✓':none?'✗':'!';
    const detail=ok?`${total}/${total}`:`${filled}/${total}`;
    return `<div style="display:flex;align-items:center;gap:5px;margin-bottom:3px"><span class="badge ${cls}" style="width:16px;text-align:center;padding:1px 0;font-size:var(--fs-2xs)">${sym}</span><span style="font-size:var(--fs-xs)">${esc(label)}</span><span style="font-size:var(--fs-2xs);color:var(--muted)">${detail}</span></div>`;
  }
  const sessCheck=sessTotal>0?`<div style="display:flex;align-items:center;gap:5px;margin-bottom:3px"><span class="badge b-ok" style="width:16px;text-align:center;padding:1px 0;font-size:var(--fs-2xs)">✓</span><span style="font-size:var(--fs-xs)">Sessions planned</span><span style="font-size:var(--fs-2xs);color:var(--muted)">${sessTotal}</span></div>`:`<div style="display:flex;align-items:center;gap:5px;margin-bottom:3px"><span class="badge b-grey" style="width:16px;text-align:center;padding:1px 0;font-size:var(--fs-2xs)">–</span><span style="font-size:var(--fs-xs);color:var(--muted)">No sessions planned</span></div>`;
  const checklistHtml=`<div style="margin-top:10px;padding-top:10px;border-top:1px solid var(--border-light)"><div style="font-size:var(--fs-2xs);font-weight:800;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">Readiness checklist</div>${sessCheck}${_rdItem('Facilitators assigned',facFill,sessTotal)}${_rdItem('Rooms assigned',roomFill,sessTotal)}</div>`;
  return `<div class="card ${tonightCardCls}">
    <h2 class="ctitle">Tonight — <span style="font-weight:400">${fmtD(d.date,{weekday:'long',day:'numeric',month:'long'})}</span></h2>
    <div class="readiness-donut" style="align-items:flex-start">
      <div>
        <div class="rdp-ring" style="background:${conic};width:72px;height:72px">
          <div class="rdp-inner" style="width:52px;height:52px;font-size:var(--fs-lg);color:${rdC}">${pct}%</div>
        </div>
        ${unstaffedCount>0?`<div style="font-size:var(--fs-2xs);color:var(--red);font-weight:700;margin-top:4px;text-align:center" title="${unstaffedCount} session${unstaffedCount!==1?'s have':' has'} no facilitator assigned yet — see \\"No facilitator assigned\\" in the Session Plan list">⚠ ${unstaffedCount} unstaffed</div>`:''}
      </div>
      <div style="flex:1">
        <div style="font-size:var(--fs-2xs);font-weight:800;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">Session Plan</div>
        ${sessHtml||'<div style="font-size:var(--fs-xs);color:var(--muted)">No sessions scheduled</div>'}
        ${checklistHtml}
        ${d.insight?`<div class="chart-insight" style="margin-top:10px">${esc(d.insight)}</div>`:''}
      </div>
    </div>
  </div>`;
}

// Upcoming readiness grid — chart_type=readiness_grid
// A zero-session night is "not_planned" — never shown with a percentage bar
// (legacy readiness_pct is 100 for zero sessions, kept for older report consumers).
function _renderUpcomingReadiness(chart){
  const rows=(chart.data||[]).slice(0,8);if(!rows.length)return '';
  return `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:10px;margin-top:12px">`+
    rows.map(r=>{
      const dateLabel=fmtD(r.date,{weekday:'short',day:'numeric',month:'short'});
      if(r.planning_status==='not_planned'||!r.sessions_total){
        return `<div style="border:1.5px solid var(--border);border-radius:8px;padding:10px" role="img" aria-label="${r.date}: not planned, no sessions scheduled">
          <div style="font-size:var(--fs-2xs);font-weight:800;color:var(--dark)">${dateLabel}</div>
          <div style="font-size:var(--fs-2xs);color:var(--muted);font-weight:700;margin-top:5px">Not planned</div>
          <div style="font-size:var(--fs-xs);color:var(--muted)">No sessions scheduled</div>
        </div>`;
      }
      const pct=r.readiness_pct||0;const col=pct>=80?'var(--ok)':pct>=60?'var(--warn)':'var(--red)';
      return `<div style="border:1.5px solid var(--border);border-radius:8px;padding:10px" role="img" aria-label="${r.date}: ${pct}% ready">
        <div style="font-size:var(--fs-2xs);font-weight:800;color:var(--dark)">${dateLabel}</div>
        <div class="pbar" style="margin:5px 0"><div style="height:100%;width:${pct}%;background:${col};border-radius:3px"></div></div>
        <div style="font-size:var(--fs-2xs);color:${col};font-weight:700">${pct}% ready</div>
        ${r.unstaffed?`<div style="font-size:var(--fs-xs);color:var(--warn-text);font-weight:700" title="${r.unstaffed} session${r.unstaffed!==1?'s have':' has'} no facilitator assigned yet — open this parade night to assign one">⚠ ${r.unstaffed} unstaffed</div>`:''}
        <div style="font-size:var(--fs-xs);color:var(--muted)">${r.sessions_total||0} sessions</div>
      </div>`;
    }).join('')+`</div>`;
}

// Heatmap — chart.data=[{label,cells:[{label,count,risk}]}]
function _renderHeatmap(chart){
  const rows=chart.data||[];if(!rows.length)return _dEmptyChart(chart.empty_state||'No data');
  const subjects=(rows[0]?.cells||[]).map(c=>c.label);
  return `<div style="overflow-x:auto"><table style="font-size:var(--fs-2xs);border-collapse:separate;border-spacing:3px">
    <thead><tr><th></th>${subjects.map(s=>`<th style="font-size:var(--fs-3xs);color:var(--muted);padding:2px 4px;white-space:nowrap;writing-mode:vertical-rl;transform:rotate(180deg);height:56px;text-align:left">${esc(s)}</th>`).join('')}</tr></thead>
    <tbody>${rows.map(row=>`<tr><td style="font-size:var(--fs-2xs);font-weight:700;padding:3px 8px;white-space:nowrap">${esc(row.label)}</td>
      ${(row.cells||[]).map(c=>{const cls=c.risk==='ok'?'hm-ok':c.risk==='warn'?'hm-warn':c.risk==='critical'?'hm-critical':'hm-empty';
        return `<td class="heatmap-cell ${cls}" style="width:34px;height:24px" title="${esc(row.label)} — ${esc(c.label)}: ${c.count} facilitator${c.count!==1?'s':''}">${c.count||0}</td>`;}).join('')}
    </tr>`).join('')}</tbody></table></div>`;
}

// Grouped bar — chart.data=[{label,<series_key>:n}], chart.series=[{key,label,color}]
function _chartGroupedBar(chart){
  const rows=chart.data||[];const series=chart.series||[];
  if(!rows.length)return _dEmptyChart(chart.empty_state||'No data available for this chart.');
  const maxV=Math.max(...rows.flatMap(r=>series.map(s=>+(r[s.key])||0)),1);
  const BAR_H=60;const gW=series.length*14+8;const totW=Math.max(rows.length*(gW+8),280);
  let html=`<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px">`+
    series.map(s=>`<span style="display:flex;align-items:center;gap:4px;font-size:var(--fs-2xs)"><span style="display:inline-block;width:10px;height:10px;background:${s.color||'var(--royal)'};border-radius:2px"></span>${esc(s.label)}</span>`).join('')+`</div>`;
  html+=`<div style="overflow-x:auto"><div style="display:flex;align-items:flex-end;gap:8px;min-width:${totW}px;height:${BAR_H+28}px">`;
  rows.forEach(row=>{
    html+=`<div style="display:flex;flex-direction:column;align-items:center;flex:1">
      <div style="display:flex;align-items:flex-end;gap:2px;height:${BAR_H}px">
        ${series.map(s=>{const v=+(row[s.key])||0;const h=Math.round(v/maxV*BAR_H);return `<div style="width:12px;height:${h}px;background:${s.color||'var(--royal)'};border-radius:2px 2px 0 0" title="${esc(s.label)}: ${v}"></div>`;}).join('')}
      </div>
      <div style="font-size:var(--fs-3xs);color:var(--muted);margin-top:3px;text-align:center;max-width:60px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(row.label||'')}</div>
    </div>`;
  });
  html+=`</div></div>`;return html;
}

// Internal: render a chart into a container div
// E5: this is the screen-reader fallback for every chart, and it was built by
// dumping raw object keys -- "coverage pct", "total items", "stage id" -- and
// every value, including UUIDs no reader can use. Keys now go through a label
// map, identifier-ish columns are dropped, and percentages get their unit.
const _CHART_COL_LABELS={
  label:'Item', name:'Name', count:'Sessions', pct:'Share', total:'Total',
  total_items:'Curriculum items', coverage_pct:'Coverage', cumulative_pct:'Cumulative',
  delivered:'Delivered', delivered_with_issue:'Delivered with issue',
  not_delivered:'Not delivered', cancelled:'Cancelled', cancelled_late:'Cancelled late',
  rescheduled:'Rescheduled', planned:'Planned', status:'Status', phase:'Phase',
  element:'Element', stage:'Training stage', expected_count:'Cadets',
  total_expected:'Cadets', display_name:'Training class',
};
const _CHART_PCT_COLS=new Set(['pct','coverage_pct','cumulative_pct']);
function _chartAccessibleTable(chart){
  const rows=chart.data||[];if(!rows.length)return'';
  // Drop identifiers and nested structures -- an id is not information to a
  // person reading the table aloud.
  const skip=new Set(['drill_id','data_quality_gap','color','classes']);
  const isIdKey=k=>/(^|_)id$/.test(k)||/_id$/.test(k)||k==='id';
  const keys=Object.keys(rows[0]||{}).filter(k=>!skip.has(k)&&!isIdKey(k));
  if(!keys.length)return'';
  const title=esc(chart.title||'Chart data');
  const head=k=>_CHART_COL_LABELS[k]||(k.charAt(0).toUpperCase()+k.slice(1).replace(/_/g,' '));
  const cell=(k,v)=>{
    if(v===null||v===undefined||v==='')return '\u2014';
    if(_CHART_PCT_COLS.has(k))return esc(String(v))+'%';
    if(k==='label'||k==='name'||k==='element')return esc(_dLabel(v));
    return esc(String(v));
  };
  const thead='<tr>'+keys.map(k=>`<th scope="col">${esc(head(k))}</th>`).join('')+'</tr>';
  const tbody=rows.map(r=>'<tr>'+keys.map(k=>`<td>${cell(k,r[k])}</td>`).join('')+'</tr>').join('');
  return`<details class="chart-data-toggle">
    <summary>Show data table \u2014 ${title}</summary>
    <div class="tw" style="margin-top:6px;font-size:var(--fs-xs)">
      <table aria-label="${title} data table"><thead>${thead}</thead><tbody>${tbody}</tbody></table>
    </div>
  </details>`;
}
function _dRenderChart(containerId,chart,renderFn,insightId){
  const el=document.getElementById(containerId);if(!el||!chart)return;
  el.innerHTML=renderFn(chart)+_chartAccessibleTable(chart);
  if(insightId&&chart.insight)_dSetInsight(insightId,chart.insight);
}

async function _refreshDashboard(){
  await _pageRefresh('dash-refresh-status', async()=>{
    await loadData();
    renderDash();
    await loadDashCharts();
  });
}

// ═══════════════════════════════════════════════════════════
//  DASHBOARD — API-DRIVEN CHART LOADER
// ═══════════════════════════════════════════════════════════
// Every dashboard chart container this page can render, paired with its
// insight div (or null) -- one shared list used for both the loading-
// skeleton reset AND the fetch-failure cleanup below, so a failed refresh
// can never leave some containers stuck on their skeleton forever or leave
// stale "success" insight text sitting next to a chart that just failed
// (previously the skeleton-reset list covered 7 containers and the failure
// cleanup covered only 2 of those 7, and neither ever touched any insight
// div at all).
const _DASH_CHART_IDS=[
  ['chart-weekly-outcomes','insight-weekly-outcomes'],
  ['chart-delivery-trend','insight-delivery-trend'],
  ['chart-session-outcomes','insight-session-outcomes'],
  ['chart-cancellation-reasons','insight-cancellation-reasons'],
  ['chart-curriculum-progress','insight-curriculum-progress'],
  ['chart-element-curriculum-progress','insight-element-curriculum-progress'],
  ['chart-class-curriculum-progress','insight-class-curriculum-progress'],
  ['chart-curriculum-backlog','insight-curriculum-backlog'],
  ['chart-facilitator-workload','insight-facilitator-workload'],
  ['chart-squadron-readiness','insight-squadron-readiness'],
  ['chart-squadron-delivery',null],
  ['chart-wing-subject-gaps','insight-wing-subject-gaps'],
  ['chart-wing-readiness','insight-wing-readiness'],
  ['chart-wing-delivery',null],
];

// DATA-CONF-01: render the data freshness indicator bar given an API data_freshness object.
// Mutates the element at the given containerId. Pass null freshness to hide.
function _renderDataConfBar(freshness, containerId){
  const el=document.getElementById(containerId||'data-conf-bar');
  if(!el)return;
  if(!freshness){el.style.display='none';return;}
  const issues=freshness.issues||[];
  const hasCovPct=(freshness.coverage_pct!=null);
  if(issues.length===0 && !hasCovPct){
    // All clean — show a brief OK state then hide
    el.className='data-conf-bar ok';
    el.innerHTML='<span class="dcb-label">✓ Data up to date</span>';
    el.style.display='flex';
    setTimeout(()=>{el.style.display='none';},4000);
    return;
  }
  const issueHtml=issues.map(i=>`<span class="dcb-issue">${esc(i)}</span>`).join('');
  const covHtml=hasCovPct?`<span class="dcb-issue">Wing coverage: ${freshness.coverage_pct}%</span>`:'';
  el.className='data-conf-bar';
  el.innerHTML=`<span class="dcb-label">⚠ Data quality</span>${issueHtml}${covHtml}`;
  el.style.display='flex';
}

// CLASS-FORECAST-01: fetch and render per-class planning forecasts on the Training Dashboard.
async function _loadClassForecasts(yearId){
  const card=document.getElementById('py-forecasts-card');
  const body=document.getElementById('fc-cards-body');
  if(!card||!body)return;
  const section=document.getElementById('dash-class-forecast-section');
  if(!yearId){card.style.display='none';if(section)section.style.display='none';return;}
  // Only squadron scope has classes to forecast; hide silently for wing/national
  const scope=effectiveScope();
  if(scope!=='squadron'){card.style.display='none';if(section)section.style.display='none';return;}
  if(section)section.style.display='';
  card.style.display='';
  body.innerHTML='<p class="muted">Loading forecasts…</p>';
  try{
    const forecasts=await api(`/api/planning/class-forecasts?year_id=${encodeURIComponent(yearId)}`);
    if(!forecasts||!forecasts.length){
      card.style.display='none';
      if(section)section.style.display='none';
      return;
    }
    const _pillLabel={'on_track':'On Track','planning_risk':'Planning Risk','critical':'Critical','not_configured':'Stage not set'};
    const _cssClass={'on_track':'on-track','planning_risk':'planning-risk','critical':'critical','not_configured':'not-configured'};
    body.innerHTML=forecasts.map(fc=>{
      const css=_cssClass[fc.status]||'';
      const pill=_pillLabel[fc.status]||esc(fc.status||'');
      return `<div class="fc-card ${css}">
        <div class="fc-card-header">
          <div>
            <div class="fc-class-name">${esc(fc.class_name||'')}</div>
            <div class="fc-stage">${fc.stage_name?esc(fc.stage_name):'<span class="muted">No stage assigned</span>'}</div>
          </div>
          <span class="fc-pill ${css}">${pill}</span>
        </div>
        <div class="fc-stats">
          <span class="fc-stat-label">Unplanned</span><span class="fc-stat-val">${fc.unplanned_requirements??'—'}</span>
          <span class="fc-stat-label">Planned</span><span class="fc-stat-val">${fc.planned_requirements??'—'}</span>
          <span class="fc-stat-label">Nights left</span><span class="fc-stat-val">${fc.remaining_parade_nights??'—'}</span>
          <span class="fc-stat-label">Time blocks</span><span class="fc-stat-val">${fc.available_time_blocks??'—'}</span>
        </div>
        ${fc.message?`<div class="fc-msg">${esc(fc.message)}</div>`:''}
      </div>`;
    }).join('');
  }catch(e){
    // 403 = scope not allowed; hide silently. Other errors show briefly.
    if(e&&(e.status===403||String(e).includes('403'))){card.style.display='none';if(section)section.style.display='none';return;}
    body.innerHTML=`<p class="muted">Could not load forecasts: ${esc(apiErr(e))}</p>`;
  }
}

async function loadDashCharts(){
  const win=document.getElementById('dash-window')?.value||'term';
  const sqn=document.getElementById('dash-sqn-filter')?.value||saBrowseSquadronId()||'';
  const params=new URLSearchParams({window:win});if(sqn)params.set('squadron_id',sqn);
  const wid=saBrowseWingId();if(wid&&!sqn)params.set('wing_id',wid);

  // Skeletons while loading
  _DASH_CHART_IDS.forEach(([id])=>{const el=document.getElementById(id);if(el)el.innerHTML='<div class="chart-skeleton"></div>';});

  let data;
  try{data=await api('/api/dashboard/charts?'+params);}
  catch(e){
    _DASH_CHART_IDS.forEach(([id,insightId])=>{
      const el=document.getElementById(id);
      if(el)el.innerHTML=_dEmptyChart('Could not load chart data. Try refreshing.');
      if(insightId)_dSetInsight(insightId,null);
    });
    return;
  }
  const charts=data.charts||{};const scope=data.scope||'squadron';
  _renderDataConfBar(data.data_freshness||null,'data-conf-bar');

  // Scope label
  const scopeEl=document.getElementById('dash-scope-label');
  if(scopeEl)scopeEl.textContent={squadron:'Squadron view',wing:'Wing view',national:'National view'}[scope]||'';

  // Section visibility
  const wingEl=document.getElementById('dash-wing-section');const natEl=document.getElementById('dash-national-section');
  if(wingEl)wingEl.style.display=scope==='wing'?'':'none';
  if(natEl)natEl.style.display=scope==='national'?'':'none';

  // A. Tonight & upcoming readiness (squadron only)
  if(scope==='squadron'){
    const tonightSec=document.getElementById('dash-tonight-section');
    if(tonightSec&&charts.tonight)tonightSec.innerHTML=_renderTonightReadiness(charts.tonight);
    else if(tonightSec)tonightSec.innerHTML='';
    const upcomingSec=document.getElementById('dash-upcoming-readiness-section');
    if(upcomingSec&&charts.upcoming_readiness){
      const ur=charts.upcoming_readiness;
      upcomingSec.innerHTML=(ur.data&&ur.data.length)?`<div class="dash-sec-sub" style="margin-top:4px">Next ${ur.data.length} parade nights</div>`+_renderUpcomingReadiness(ur):'';
      if(ur.insight)upcomingSec.innerHTML+=`<div class="chart-insight" style="margin-top:8px">${esc(ur.insight)}</div>`;
    }else if(upcomingSec)upcomingSec.innerHTML='';
  }

  // B. Delivery charts
  _dRenderChart('chart-weekly-outcomes',charts.weekly_outcomes,_chartStackedBar,'insight-weekly-outcomes');
  _dSetExp('exp-weekly-outcomes',charts.weekly_outcomes?.explanation);
  _dRenderChart('chart-delivery-trend',charts.delivery_trend,_chartLine,'insight-delivery-trend');
  _dSetExp('exp-delivery-trend',charts.delivery_trend?.explanation);
  _dRenderChart('chart-session-outcomes',charts.session_outcomes,_chartDonut,'insight-session-outcomes');
  _dRenderChart('chart-cancellation-reasons',charts.cancellation_reasons,_chartHBar,'insight-cancellation-reasons');
  // DASH-15: delivery forecast — hidden when no data
  (function(){
    const fc=charts.delivery_forecast;const d=fc?.data||{};
    const hasData=(d.ytd_total_terminal>0||d.remaining_planned>0);
    const card=document.getElementById('card-delivery-forecast');
    if(card)card.style.display=hasData?'':'none';
    if(hasData)_dRenderChart('chart-delivery-forecast',fc,_chartDeliveryForecast,'insight-delivery-forecast');
  })();
  // DASH-06: when the top cancellation reason is a data quality gap, surface an
  // actionable prompt so staff know to update those sessions — not display it as
  // an inert bar only a data analyst would notice.
  (function(){
    const cr=charts.cancellation_reasons;const rows=(cr&&cr.data)||[];
    if(!rows.length||!rows[0].data_quality_gap)return;
    const gapCount=rows[0].count||rows[0].value||0;
    const total=rows.reduce((s,r)=>s+(+(r.count||r.value||0)),0);
    if(!total||gapCount/total<0.15)return; // only prompt when ≥15% of reasons unknown
    const el=document.getElementById('chart-cancellation-reasons');
    if(!el)return;
    const pct=Math.round(gapCount/total*100);
    el.insertAdjacentHTML('beforeend',`<div class="alert a-warn" style="margin-top:8px;font-size:var(--fs-xs)"><strong>${pct}% of cancellations have no reason recorded (${gapCount} of ${total}).</strong> Recording reasons helps identify patterns. Open each affected session and add a reason under Outcome.</div>`);
  })();

  // C. Curriculum
  _dRenderChart('chart-curriculum-progress',charts.curriculum_progress,_chartStackedBarH,'insight-curriculum-progress');
  _dSetExp('exp-curriculum-progress',charts.curriculum_progress?.explanation);
  _dRenderChart('chart-element-curriculum-progress',charts.element_curriculum_progress,_chartStackedBarH,'insight-element-curriculum-progress');
  _dSetExp('exp-element-curriculum-progress',charts.element_curriculum_progress?.explanation);
  // E2/CLASS-07: one card over both payloads. Shown when either has classes.
  const clsCard=document.getElementById('card-class-overview');
  const hasProg=(charts.class_curriculum_progress?.data||[]).length>0;
  const hasCE=(charts.class_enrollment?.data||[]).length>0;
  if(clsCard) clsCard.style.display=(hasProg||hasCE)?'':'none';
  const clsHost=document.getElementById('chart-class-overview');
  if(clsHost) clsHost.innerHTML=_chartClassTable(charts.class_curriculum_progress,charts.class_enrollment);
  _dSetExp('exp-class-curriculum-progress',charts.class_curriculum_progress?.explanation);
  if(charts.class_curriculum_progress?.insight) _dSetInsight('insight-class-curriculum-progress',charts.class_curriculum_progress.insight);
  if(charts.class_enrollment?.insight) _dSetInsight('insight-class-enrollment',charts.class_enrollment.insight);
  _dRenderChart('chart-curriculum-backlog',charts.curriculum_backlog,_chartHBar,'insight-curriculum-backlog');
  _dRenderChart('chart-facilitator-workload',charts.facilitator_workload,_chartHBar,'insight-facilitator-workload');

  // Wing charts
  if(scope==='wing'){
    _dRenderChart('chart-squadron-readiness',charts.squadron_readiness,_chartHBar,'insight-squadron-readiness');
    _dRenderChart('chart-squadron-delivery',charts.squadron_delivery_comparison,_chartGroupedBar);
    _dRenderChart('chart-wing-subject-gaps',charts.wing_subject_area_gaps,_renderHeatmap,'insight-wing-subject-gaps');
  }

  // National charts
  if(scope==='national'){
    _dRenderChart('chart-wing-readiness',charts.wing_readiness,_chartHBar,'insight-wing-readiness');
    _dRenderChart('chart-wing-delivery',charts.wing_delivery_comparison,_chartGroupedBar);
  }
}

// ═══════════════════════════════════════════════════════════
//  FACILITATORS — VISUAL STATISTICS
// ═══════════════════════════════════════════════════════════
async function _populateFacRankList(){
  // DEF-04: load canonical AAFC rank catalogue from backend single source of truth.
  // Called once on facilitator page load; gracefully falls back to empty datalist
  // (user can still type a rank freely) if the endpoint is unavailable.
  const dl=document.getElementById('fac-rank-list');
  if(!dl||dl.childElementCount>0)return; // already populated
  try{
    const d=await api('/api/facilitators/ranks');
    dl.innerHTML=(d.ranks||[]).map(r=>`<option value="${esc(r.code)}">${esc(r.label)}</option>`).join('');
  }catch(_){}
}
async function loadFacilitatorStats(){
  _populateFacRankList();
  const chartIds=['fac-chart-status','fac-chart-workload','fac-chart-spof','fac-chart-gaps','fac-chart-type'];
  chartIds.forEach(id=>{const el=document.getElementById(id);if(el)el.innerHTML='<div class="chart-skeleton"></div>';});
  let data;
  const sqn=saBrowseSquadronId();
  try{data=await api('/api/dashboard/charts?window=term'+(sqn?'&squadron_id='+encodeURIComponent(sqn):''));}
  // Skeletons must not be left spinning forever on failure -- same
  // fetch-failure-cleanup reasoning as loadDashCharts's own _DASH_CHART_IDS
  // loop (see that function's comment).
  catch(e){
    chartIds.forEach(id=>{const el=document.getElementById(id);if(el)el.innerHTML=_dEmptyChart('Could not load chart data. Try refreshing.');});
    return;
  }
  const charts=data.charts||{};
  _dRenderChart('fac-chart-status',charts.facilitator_status_distribution,_chartDonut,'fac-insight-status');
  _dRenderChart('fac-chart-workload',charts.facilitator_workload,_chartHBar,'fac-insight-workload');
  _dRenderChart('fac-chart-spof',charts.subject_area_resilience,_chartHBar,'fac-insight-spof');
  _dRenderChart('fac-chart-gaps',charts.facilitator_repeated_gaps,_chartHBar,'fac-insight-gaps');
  _dRenderChart('fac-chart-type',charts.facilitator_type_distribution,_chartHBar,'fac-insight-type');
}

function _chartDeliveryForecast(chart){
  const d=chart.data||{};
  const rate=d.delivery_rate_pct;
  const remaining=d.remaining_planned;
  const projDel=d.projected_delivered;
  const projMiss=d.projected_missed;
  const hasHistory=(d.ytd_total_terminal>0);
  const hasForecast=(projDel!=null);

  if(!hasHistory&&!remaining)return _dEmptyChart(chart.empty_state||'Not enough data to forecast.');

  const rateColor=rate!=null?(rate>=80?'var(--ok)':rate>=60?'var(--warn)':'var(--red)'):'var(--muted)';
  const missColor=hasForecast&&projMiss>0?'var(--warn)':'var(--ok)';

  let html='<div style="display:flex;flex-wrap:wrap;gap:12px;align-items:flex-start">';

  if(hasHistory){
    html+=`<div style="flex:1;min-width:100px;text-align:center;padding:8px 4px">
      <div style="font-size:var(--fs-xs);color:var(--muted);margin-bottom:2px">Current rate</div>
      <div style="font-size:var(--fs-4xl);font-weight:800;color:${rateColor};line-height:1.1">${rate!=null?rate+'%':'—'}</div>
      <div style="font-size:var(--fs-2xs);color:var(--muted)">${d.ytd_delivered} of ${d.ytd_total_terminal} sessions delivered YTD</div>
    </div>`;
  }

  if(remaining>0){
    html+=`<div style="flex:1;min-width:100px;text-align:center;padding:8px 4px">
      <div style="font-size:var(--fs-xs);color:var(--muted);margin-bottom:2px">Remaining planned</div>
      <div style="font-size:var(--fs-4xl);font-weight:800;color:var(--text);line-height:1.1">${remaining}</div>
      <div style="font-size:var(--fs-2xs);color:var(--muted)">sessions still ahead</div>
    </div>`;
  }

  if(hasForecast){
    html+=`<div style="flex:1;min-width:100px;text-align:center;padding:8px 4px">
      <div style="font-size:var(--fs-xs);color:var(--muted);margin-bottom:2px">Projected to deliver</div>
      <div style="font-size:var(--fs-4xl);font-weight:800;color:var(--ok);line-height:1.1">${projDel}</div>
      <div style="font-size:var(--fs-2xs);color:var(--muted)">of ${remaining} remaining</div>
    </div>
    <div style="flex:1;min-width:100px;text-align:center;padding:8px 4px">
      <div style="font-size:var(--fs-xs);color:var(--muted);margin-bottom:2px">At risk</div>
      <div style="font-size:var(--fs-4xl);font-weight:800;color:${missColor};line-height:1.1">${projMiss}</div>
      <div style="font-size:var(--fs-2xs);color:var(--muted)">projected non-delivery</div>
    </div>`;
  }else if(remaining>0&&!hasHistory){
    html+=`<div style="flex:2;padding:8px 4px">
      <div style="font-size:var(--fs-sm);color:var(--muted)">${remaining} sessions planned for the rest of the year. Record outcomes on past Parade Nights to enable the forecast.</div>
    </div>`;
  }

  html+='</div>';
  return html;
}

function _chartTermYtd(chart){
  const d=chart.data||{};
  const hasTerm=(d.current_term!=null&&d.current_term_pct!=null);
  const hasDelta=(hasTerm&&d.prev_term!=null&&d.delta_pct!=null);
  const hasYtd=(d.ytd_total>0&&d.ytd_pct!=null);
  if(!hasYtd&&!hasTerm)return _dEmptyChart(chart.empty_state||'No term data available. Set training term on Parade Nights to enable this view.');

  function _statBox(label,pct,subLabel,delta){
    const color=pct!=null?(pct>=80?'var(--ok)':pct>=60?'var(--warn)':'var(--red)'):'var(--muted)';
    const deltaHtml=delta!=null
      ?`<div style="font-size:var(--fs-xs);color:${delta>0?'var(--ok)':delta<0?'var(--red)':'var(--muted)'};">`+
        `${delta>0?'▲':'▼'} ${Math.abs(delta)} pp vs ${esc(d.prev_term||'prior term')}</div>`:'';
    return `<div style="flex:1;text-align:center;padding:8px 4px">
      <div style="font-size:var(--fs-xs);color:var(--muted);margin-bottom:2px">${esc(label)}</div>
      <div style="font-size:var(--fs-4xl);font-weight:800;color:${color};line-height:1.1">${pct!=null?pct+'%':'—'}</div>
      ${subLabel?`<div style="font-size:var(--fs-2xs);color:var(--muted)">${esc(subLabel)}</div>`:''}
      ${deltaHtml}
    </div>`;
  }

  let boxes='';
  if(hasYtd) boxes+=_statBox('Year to Date',d.ytd_pct,`${d.ytd_delivered} of ${d.ytd_total} sessions`);
  if(hasTerm) boxes+=_statBox(esc(d.current_term||'Current term'),d.current_term_pct,'',hasDelta?d.delta_pct:null);
  if(d.prev_term!=null&&d.prev_term_pct!=null) boxes+=_statBox(esc(d.prev_term||'Prior term'),d.prev_term_pct,'');

  return `<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:flex-start">${boxes}</div>`;
}

async function _loadDashStrategic(){
  const btn=document.getElementById('btn-load-strategic');
  if(btn){btn.textContent='Loading…';btn.disabled=true;}
  const win=document.getElementById('dash-window')?.value||'term';
  const wid=saBrowseWingId();
  let data;
  try{data=await api('/api/dashboard/charts/strategic?window='+win+(wid?'&wing_id='+encodeURIComponent(wid):''));}
  catch(e){if(btn){btn.textContent='Load Resilience Charts ↓';btn.disabled=false;}return;}
  const charts=data.charts||{};
  const sec=document.getElementById('dash-strategic-section');if(sec)sec.style.display='';
  _dRenderChart('chart-capability-dependency',charts.capability_dependency,_chartHBar,'insight-capability-dependency');
  _dRenderChart('chart-subject-area-resilience',charts.subject_area_resilience,_chartHBar,'insight-subject-area-resilience');
  _dRenderChart('chart-facilitator-status',charts.facilitator_status_distribution,_chartDonut,'insight-facilitator-status');
  _dRenderChart('chart-facilitator-type',charts.facilitator_type_distribution,_chartHBar,'insight-facilitator-type');
  _dRenderChart('chart-facilitator-gaps',charts.facilitator_repeated_gaps,_chartHBar,'insight-facilitator-gaps');
  // Stage 9, 2026-08-05: backend already computed this ("who needs a
  // substitute" -- upcoming sessions clashing with recorded facilitator
  // leave) and Planning Workspace already renders it; connected-frontend
  // never had a card for it at all.
  _dRenderChart('chart-facilitator-leave-impact',charts.facilitator_leave_impact,_chartHBar,'insight-facilitator-leave-impact');
  _dRenderChart('chart-long-term-trend',charts.long_term_delivery_trend,_chartLine);
  const ytdCard=document.getElementById('card-term-ytd');
  if(ytdCard){
    const ytd=charts.term_comparison_ytd;
    const d=ytd?.data||{};
    const hasData=(d.ytd_total>0||d.current_term!=null);
    ytdCard.style.display=hasData?'':'none';
  }
  _dRenderChart('chart-term-ytd',charts.term_comparison_ytd,_chartTermYtd,'insight-term-ytd');
  if(btn)btn.style.display='none';
}

function drillDashChart(chartId,drillId){
  // Drill to sessions filtered by the chart's drill context (phase, status, week)
  const sess=allSess().filter(s=>{
    if(chartId==='curriculum_progress'||chartId==='curriculum_backlog')return s.phase===drillId;
    if(chartId==='element_curriculum_progress')return s.element===drillId;
    if(chartId==='cancellation_reasons'||chartId==='cancellation_pareto'){
      // Match the backend's 60-char truncation so reason labels align with session data
      const raw=(s.status==='cancelled'?s.cancelled_reason||'':s.not_delivered_reason||'').trim();
      if(drillId==='__no_reason__')
        return (s.status==='cancelled'||s.status==='not_delivered')&&!raw;
      const trunc=raw.length>60?raw.substring(0,60)+'…':raw;
      return trunc===drillId;
    }
    return s.status===drillId;
  });
  const title=drillId==='__no_reason__'?'Reason not recorded — review and update':drillId;
  showDrill('dash-drill','dash-drill-title','dash-drill-body',title,sess);
}

function renderDash(){
  const info=getCurrentUnitInfo();
  document.getElementById('dash-title').textContent=info.name+' — Training Dashboard';
  const banner=document.getElementById('dash-setup-banner');
  if(banner){
    const show=S.role==='sqn_admin'&&!P.currentYearId;
    banner.style.display=show?'':'none';
    if(show)banner.innerHTML='<div class="card" style="border-left:4px solid var(--blue);background:var(--accent-light);display:flex;align-items:flex-start;gap:14px;padding:14px 16px"><div style="flex:1"><div style="font-size:var(--fs-xs);font-weight:800;color:var(--royal);margin-bottom:4px;text-transform:uppercase;letter-spacing:.06em">No active training year</div><div style="font-size:var(--fs-sm);color:var(--text-2);margin-bottom:10px">Create a training year to activate your schedule, parade nights, and training program.</div><button class="btn btn-primary btn-sm" onclick="nav(\'settings\')">Set up this year →</button></div></div>';
  }
  loadDashCharts();
  _loadClassForecasts(P.currentYearId||null);
}

// ═══════════════════════════════════════════════════════════
//  WING OVERVIEW
// ═══════════════════════════════════════════════════════════
// ── Visual helpers (reuse existing palette) ──
function pctCls(p){ p=+p||0; return p>=67?'':p>=34?'amber':'red'; }   // '' = green
function ndCls(n){ n=+n||0; return n===0?'':n<=2?'amber':'red'; }
function miniBar(p,cls){ p=Math.max(0,Math.min(100,+p||0)); return `<div class="cellbar"><div class="mini ${cls!==undefined?cls:pctCls(p)}"><i style="width:${p}%"></i></div><span>${p}%</span></div>`; }
function statusBadge(row){
  if(row.no_published_plan)return '<span class="badge b-red">No published plan</span>';
  if(row.no_future_plan)return '<span class="badge b-amber">No future plan</span>';
  if((row.delivered||0)>0)return '<span class="badge b-ok">Active</span>';
  if((row.nights||0)>0)return '<span class="badge b-blue">Planned</span>';
  return '<span class="badge b-amber">No data</span>';
}
function readinessDot(v){
  if(v===null||v===undefined)return '<span class="dot n" aria-hidden="true"></span><span class="sr-only">No data</span>—';
  const c=v>=80?'g':v>=60?'a':'r';
  const label=v>=80?'On track':v>=60?'At risk':'Critical';
  return `<span class="dot ${c}" aria-hidden="true"></span><span class="sr-only">${label}:</span>${v}`;
}
function heatColor(p){ p=+p||0; return p>=67?'#1a7f4b':p>=34?'#c97a00':p>0?'#e51937':'#c2ccd6'; }

// ═══ WING DASHBOARD (backend: /api/reports/wing-overview + wing-phase-coverage) ═══
// ═══════════════════════════════════════════════════════════
//  TRAINING DASHBOARD — Wing/National command sections A + B
// ═══════════════════════════════════════════════════════════
// Extends the existing Squadron dashboard upward. Every chart shows Purpose/
// Measure/Action via an info toggle, an Assessment line, and a data-confidence
// footnote — reusing the existing _chartStackedBar/_chartLine/_chartStackedBarH
// renderers wherever the backend's chart shape already matches them (the
// backend deliberately reuses those same chart_ids for that reason), and
// adding new renderers only for the genuinely new shapes (readiness matrix,
// risk timeline, 100%-stacked bars, Pareto with cumulative %).
const _CMD_WINDOW_LABELS={week:'This Week',term:'This Term',semester:'Semester',year:'Year'};
const _CMD_STATUS_SYMBOL={ok:'✓',warning:'▲',critical:'✕',no_data:'—'};
const _CMD_STATUS_COLOR={ok:'var(--ok)',warning:'var(--warn)',critical:'var(--red)',no_data:'var(--muted)'};
const _CMD_TREND_SYMBOL={up:'▲ improving',down:'▼ declining',flat:'▬ steady',no_data:'no prior data'};
let _cmdReadinessRows=[];
let _cmdInfoSeq=0;

function _cmdInfoToggle(chart){
  const id='cmd-info-'+(_cmdInfoSeq++);
  return `<button class="btn btn-xs" style="font-size:var(--fs-2xs);padding:2px 6px" onclick="var e=document.getElementById('${id}');e.style.display=e.style.display==='none'?'block':'none'" aria-expanded="false" aria-controls="${id}">ℹ Purpose</button>
    <div id="${id}" style="display:none;font-size:var(--fs-xs);color:var(--text-2);background:var(--surface-2);border:1px solid var(--border);border-radius:6px;padding:8px 10px;margin-top:6px;width:100%">
      <div><strong>Purpose:</strong> ${esc(chart.purpose||'')}</div>
      <div style="margin-top:4px"><strong>Measure:</strong> ${esc(chart.measure||'')}</div>
      <div style="margin-top:4px"><strong>Action:</strong> ${esc(chart.action||'')}</div>
    </div>`;
}

function _cmdCard(chart, bodyHtml){
  if(!chart)return '';
  const assessment=chart.assessment||chart.insight||'';
  let confHtml='';
  const c=chart.data_confidence;
  if(c){
    if(c.units_reporting!==undefined){
      confHtml=`<div style="font-size:var(--fs-2xs);color:var(--muted);margin-top:6px">Data confidence: ${c.units_reporting} of ${c.units_expected} unit(s) reporting${c.completeness_pct!=null?` (${c.completeness_pct}% complete)`:''}.</div>`;
    } else if(c.note){
      confHtml=`<div style="font-size:var(--fs-2xs);color:var(--muted);margin-top:6px">${esc(c.note)}</div>`;
    }
  }
  return `<div class="card" style="margin-bottom:14px">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;flex-wrap:wrap">
      <h2 class="ctitle" style="margin-bottom:0">${esc(chart.title||'')}</h2>
      ${_cmdInfoToggle(chart)}
    </div>
    ${assessment?`<div style="font-size:var(--fs-sm);color:var(--text-2);margin:6px 0 10px">${esc(assessment)}</div>`:''}
    <div>${bodyHtml}</div>
    ${confHtml}
  </div>`;
}

function _cmdCell(cell){
  if(!cell)return '<span class="muted">—</span>';
  const sym=_CMD_STATUS_SYMBOL[cell.status]||'—';
  const col=_CMD_STATUS_COLOR[cell.status]||'var(--muted)';
  const label=cell.data_available===false?'Data not available':
    (cell.denominator?`${cell.numerator}/${cell.denominator}`:(cell.numerator!=null?String(cell.numerator):'—'));
  const title=cell.exception_reason||'';
  return `<span style="color:${col};font-weight:700" title="${esc(title)}">${sym}</span> <span style="font-size:var(--fs-xs)" title="${esc(title)}">${esc(label)}</span>`;
}

// A1 — readiness matrix: Wing rows=Squadrons, National rows=Wings.
function _renderReadinessMatrix(chart,scope){
  const rows=chart.data||[];
  if(!rows.length)return _dEmptyChart(chart.empty_state||'No data available for this chart.');
  const cols=chart.columns||[];
  const colLabels={sessions_planned:'Sessions planned',curriculum_allocated:'Curriculum',
    facilitator_confirmed:'Facilitator',facility_confirmed:'Facility',
    equipment_confirmed:'Equipment',overall_readiness:'Overall'};
  let html='<div class="tw"><table><thead><tr><th>Unit</th>'+
    cols.map(c=>`<th style="text-align:center;font-size:var(--fs-2xs)">${esc(colLabels[c]||c)}</th>`).join('')+
    '<th style="text-align:center;font-size:var(--fs-2xs)">Trend</th></tr></thead><tbody>';
  rows.forEach(r=>{
    html+=`<tr class="drow" onclick="cmdDrillReadiness('${r.unit_id}','${scope}')" title="${esc(r.exception_reason||'')}">
      <td style="font-weight:800">${esc(r.label)}${r.name&&r.name!==r.label?` <span class="muted" style="font-weight:400;font-size:var(--fs-2xs)">${esc(r.name)}</span>`:''}</td>
      ${cols.map(c=>`<td style="text-align:center">${_cmdCell(r[c])}</td>`).join('')}
      <td style="text-align:center;font-size:var(--fs-2xs);color:var(--muted)">${_CMD_TREND_SYMBOL[r.trend]||'—'}</td>
    </tr>`;
  });
  html+='</tbody></table></div>';
  return html;
}

function cmdDrillReadiness(unitId,scope){
  const r=_cmdReadinessRows.find(x=>x.unit_id===unitId);
  const panelId='cmd-drill-'+(scope||'national');
  const p=document.getElementById(panelId); if(!r||!p)return;
  p.className='drill-panel show';
  const cols=['sessions_planned','curriculum_allocated','facilitator_confirmed','facility_confirmed','equipment_confirmed','overall_readiness'];
  const colLabels={sessions_planned:'Sessions planned',curriculum_allocated:'Curriculum allocated',
    facilitator_confirmed:'Facilitator confirmed',facility_confirmed:'Facility confirmed',
    equipment_confirmed:'Equipment confirmed',overall_readiness:'Overall readiness'};
  p.innerHTML=`<div class="drill-hdr"><div class="drill-title">${esc(r.name||r.label)} — next parade night readiness</div><button class="modal-x" aria-label="Close" onclick="document.getElementById('${panelId}').className='drill-panel'">×</button></div>
    <div class="tw"><table><tbody>
    ${cols.map(c=>`<tr><td style="font-weight:700">${esc(colLabels[c])}</td><td>${_cmdCell(r[c])}</td><td style="font-size:var(--fs-xs);color:var(--muted)">${esc((r[c]&&r[c].exception_reason)||'')}</td></tr>`).join('')}
    </tbody></table></div>
    <div style="font-size:var(--fs-xs);color:var(--muted);margin-top:10px">Trend vs previous parade night: ${_CMD_TREND_SYMBOL[r.trend]||'—'}. Last updated: ${r.last_update?new Date(r.last_update).toLocaleString('en-AU',{day:'2-digit',month:'short',year:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}):'—'}.</div>`;
  p.scrollIntoView({behavior:'smooth',block:'start'});
}

// A2 — eight-week risk forecast: weekly stacked timeline + supporting evidence table.
function _renderRiskTimeline(chart){
  const weekly=chart.weekly||[];
  const items=chart.data||[];
  let html='';
  if(weekly.length){
    const cats=[['no_facilitator','No facilitator','#e51937'],['no_facility','No facility','#f57c00'],
      ['curriculum_not_allocated','Curriculum','#8a93a6'],['activity_conflict','Activity conflict','#455560'],
      ['holiday_conflict','Holiday conflict','#51b0e3']];
    const maxV=Math.max(...weekly.map(w=>cats.reduce((s,cc)=>s+(w[cc[0]]||0),0)),1);
    html+=`<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px">`+
      cats.map(cc=>`<span style="display:flex;align-items:center;gap:4px;font-size:var(--fs-2xs)"><span style="display:inline-block;width:10px;height:10px;background:${cc[2]};border-radius:2px"></span>${esc(cc[1])}</span>`).join('')+`</div>`;
    html+=`<div style="overflow-x:auto"><div style="display:flex;align-items:flex-end;gap:3px;min-width:${Math.max(weekly.length*44,280)}px;height:108px">`;
    weekly.forEach(w=>{
      const total=cats.reduce((s,cc)=>s+(w[cc[0]]||0),0);
      const hPx=Math.round(total/maxV*80);
      html+=`<div style="flex:1;display:flex;flex-direction:column;align-items:center;min-width:32px">
        <div style="width:100%;max-width:36px;height:${hPx}px;display:flex;flex-direction:column-reverse;border-radius:3px 3px 0 0;overflow:hidden">
          ${cats.map(cc=>{const v=w[cc[0]]||0;return v?`<div style="flex:${v};width:100%;background:${cc[2]}" title="${esc(cc[1])}: ${v}"></div>`:'';}).join('')}
        </div>
        <div style="font-size:var(--fs-3xs);color:var(--muted);margin-top:3px" title="${esc(w.label)}">${esc(w.label)}</div>
      </div>`;
    });
    html+='</div></div>';
  } else {
    html+=_dEmptyChart(chart.empty_state||'No training risk identified in the next 8 weeks.');
  }
  if(items.length){
    html+=`<div class="tw" style="margin-top:10px"><table><thead><tr><th>Date</th><th>Unit</th><th>Category</th><th style="text-align:center">Sessions</th><th>Severity</th></tr></thead><tbody>`+
      items.slice(0,20).map(it=>`<tr><td style="font-size:var(--fs-xs)">${esc(it.date)}</td><td style="font-weight:700">${esc(it.unit_label)}</td><td style="font-size:var(--fs-xs)">${esc(it.category_label)}</td><td style="text-align:center">${it.affected_sessions}</td><td><span class="badge ${it.severity==='high'?'b-red':'b-amber'}">${esc(_cap(it.severity))}</span></td></tr>`).join('')+
      `</tbody></table></div>`;
    if(items.length>20)html+=`<div style="font-size:var(--fs-2xs);color:var(--muted);margin-top:4px">Showing 20 of ${items.length} items — refine using Parade Nights for the full list.</div>`;
  }
  return html;
}

// B3 — session outcomes by unit, 100%-stacked (never absolute-value stacked,
// which would let a low-volume unit's bar look artificially small).
function _chartStackedBar100(chart){
  const rows=chart.data||[];const series=chart.series||[];
  if(!rows.length)return _dEmptyChart(chart.empty_state||'No data available for this chart.');
  let html=`<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px">`+
    series.map(s=>`<span style="display:flex;align-items:center;gap:4px;font-size:var(--fs-2xs)"><span style="display:inline-block;width:10px;height:10px;background:${s.color||'var(--royal)'};border-radius:2px"></span>${esc(s.label)}</span>`).join('')+`</div>`;
  rows.forEach(row=>{
    const total=row.total||0;
    html+=`<div class="ph-row" style="margin-bottom:6px" role="img" aria-label="${esc(row.label)}: ${total} sessions">
      <div class="ph-name" style="min-width:70px;font-size:var(--fs-xs)">${esc(_dLabel(row.label))}</div>
      <div class="ph-bar" style="flex:1">
        <div style="display:flex;height:16px;border-radius:3px;overflow:hidden;background:var(--bg)">
          ${total?series.map(s=>{const pct=(row.pct&&row.pct[s.key])||0;return pct?`<div style="flex:${pct};background:${s.color};height:100%" title="${esc(s.label)}: ${row.counts[s.key]} (${pct}%)"></div>`:'';}).join(''):'<div style="flex:1;background:var(--lgrey)" title="No sessions"></div>'}
        </div>
      </div>
      <div class="ph-cnt" style="min-width:44px;text-align:right;font-size:var(--fs-2xs);color:var(--muted)">${total}</div>
    </div>`;
  });
  return html;
}

// B4 — cancellation/non-delivery Pareto: ranked bars + cumulative percentage.
function _renderPareto(chart){
  const rows=chart.data||[];
  if(!rows.length)return _dEmptyChart(chart.empty_state||'No data available for this chart.');
  const maxV=Math.max(...rows.map(r=>r.count),1);
  return rows.map(r=>{
    const w=Math.round(r.count/maxV*100);
    const isGap=!!r.data_quality_gap;
    const drill=r.drill_id?`onclick="drillDashChart('${esc(chart.chart_id)}','${esc(r.drill_id)}')" style="cursor:pointer"`:'';
    return `<div class="ph-row" style="margin-bottom:5px" role="img" aria-label="${esc(r.label)}: ${r.count}, cumulative ${r.cumulative_pct}%" ${drill}>
      <div class="ph-name" style="min-width:130px;font-size:var(--fs-xs);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;${isGap?'font-style:italic;color:var(--muted)':''}" title="${esc(r.label)}">${isGap?'ⓘ ':''}${esc(_dLabel(r.label).substring(0,40))}</div>
      <div class="ph-bar" style="flex:1"><div class="pbar"><div style="height:100%;width:${w}%;background:${isGap?'var(--muted)':'var(--royal)'};border-radius:3px"></div></div></div>
      <div class="ph-cnt" style="min-width:96px;text-align:right;font-size:var(--fs-2xs);color:var(--muted)">${r.count} · cum. ${r.cumulative_pct}%</div>
    </div>`;
  }).join('');
}

async function loadCommandDashboard(scope){
  const containerId=scope==='wing'?'cmd-dash-wing':'cmd-dash-national';
  const host=document.getElementById(containerId); if(!host)return;
  host.innerHTML='<div class="card"><h1 class="ph-title" style="font-size:var(--fs-lg)">Training Dashboard</h1><div class="muted" style="font-size:var(--fs-sm)">Loading…</div></div>';
  const win=S.cmdWindow||'term';
  const wingId=(S.role==='system_admin')?saBrowseWingId():null;
  let url='/api/dashboard/command?window='+encodeURIComponent(win);
  if(wingId)url+='&wing_id='+encodeURIComponent(wingId);
  let d;
  try{ d=await api(url); }
  catch(e){ host.innerHTML=`<div class="card"><div class="sc-status-err">Training Dashboard unavailable: ${esc(apiErr(e))}</div></div>`; return; }
  if(d.error==='no_wing_scope'){ host.innerHTML=''; return; }

  _cmdReadinessRows=(d.sections&&d.sections.A&&d.sections.A.readiness_matrix&&d.sections.A.readiness_matrix.data)||[];

  const proxyBanner=proxyActive()?`<div style="font-size:var(--fs-xs);color:var(--text);background:var(--warn-bg);border-radius:6px;padding:4px 8px;margin-bottom:8px;display:inline-block">Delegated Intervention active — protected writes enabled.</div>`:''/* DES-H04 */;
  let html=`<div class="ph" style="margin-bottom:6px">
    <h1 class="ph-title">Training Dashboard</h1>
    <div class="ph-sub">
      Viewing as: ${esc(S.role||'')} · Scope: ${esc(d.scope==='wing'?'Wing':'National')}${d.wing_name?' — '+esc(d.wing_name):''} ·
      Period: <select id="cmd-window-sel" onchange="S.cmdWindow=this.value;loadCommandDashboard('${scope}')" style="font-size:var(--fs-xs);padding:2px 4px;border:1px solid var(--border);border-radius:4px" aria-label="Reporting period">
        ${Object.entries(_CMD_WINDOW_LABELS).map(([k,l])=>`<option value="${k}"${k===win?' selected':''}>${l}</option>`).join('')}
      </select>
      · Data current as at ${new Date(d.generated_at).toLocaleString('en-AU',{day:'2-digit',month:'short',year:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false})}
      · Data confidence: ${d.data_confidence.units_reporting}/${d.data_confidence.units_expected} unit(s) reporting
    </div>
    ${proxyBanner}
  </div>`;

  html+=`<h2 style="font-size:var(--fs-xs);font-weight:800;color:var(--dark);text-transform:uppercase;letter-spacing:.03em;margin:14px 0 6px">A — Immediate Training Readiness</h2>`;
  html+=_cmdCard(d.sections.A.readiness_matrix,_renderReadinessMatrix(d.sections.A.readiness_matrix,scope));
  html+=_cmdCard(d.sections.A.risk_forecast,_renderRiskTimeline(d.sections.A.risk_forecast));
  html+=_cmdCard(d.sections.A.immediate_issues,_chartStackedBarH(d.sections.A.immediate_issues));

  html+=`<h2 style="font-size:var(--fs-xs);font-weight:800;color:var(--dark);text-transform:uppercase;letter-spacing:.03em;margin:18px 0 6px">B — Training Delivery Performance</h2>`;
  html+=_cmdCard(d.sections.B.weekly_delivered,_chartStackedBar(d.sections.B.weekly_delivered));
  html+=_cmdCard(d.sections.B.reliability_trend,_chartLine(d.sections.B.reliability_trend));
  html+=_cmdCard(d.sections.B.outcomes_by_unit,_chartStackedBar100(d.sections.B.outcomes_by_unit));
  html+=_cmdCard(d.sections.B.cancellation_pareto,_renderPareto(d.sections.B.cancellation_pareto));

  html+=`<div class="drill-panel" id="cmd-drill-${scope}"></div>`;
  html+=`<h2 style="font-size:var(--fs-xs);font-weight:800;color:var(--dark);text-transform:uppercase;letter-spacing:.03em;margin:18px 0 6px">C — System Adoption</h2>`;
  html+=`<div class="card" style="padding:12px 16px"><div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
    <span style="font-size:var(--fs-sm);color:var(--muted)">Shows squadron-level system activity. Not a surveillance tool — aggregates only.</span>
    <select id="adoption-period-sel-${scope}" style="font-size:var(--fs-xs);padding:3px 6px;border:1px solid var(--border);border-radius:4px" aria-label="Adoption period">
      <option value="7d">Last 7 days</option>
      <option value="30d" selected>Last 30 days</option>
      <option value="term">This term (90 days)</option>
      <option value="year">This year</option>
    </select>
    <button class="btn btn-out" style="font-size:var(--fs-xs);padding:4px 10px" onclick="_loadAdoptionData('${scope}')">Load Adoption Data ↓</button>
  </div>
  <div id="adoption-content-${scope}" style="margin-top:10px"></div></div>`;
  host.innerHTML=html;
}

async function _loadAdoptionData(scope){
  const container=document.getElementById('adoption-content-'+scope); if(!container)return;
  const periodSel=document.getElementById('adoption-period-sel-'+scope);
  const period=periodSel?periodSel.value:'30d';
  const wingId=(S.role==='system_admin')?saBrowseWingId():null;
  let url='/api/dashboard/adoption?period='+encodeURIComponent(period);
  if(wingId)url+='&wing_id='+encodeURIComponent(wingId);
  container.innerHTML='<div class="muted" style="font-size:var(--fs-sm)">Loading…</div>';
  let d;
  try{ d=await api(url); }
  catch(e){ container.innerHTML=`<div class="sc-status-err" style="font-size:var(--fs-sm)">Adoption data unavailable: ${esc(apiErr(e))}</div>`; return; }
  if(!d.units||!d.units.length){ container.innerHTML='<div class="muted" style="font-size:var(--fs-sm)">No squadron data for this period.</div>'; return; }
  const since=d.since?'Since '+fmtD(d.since,{day:'numeric',month:'short',year:'numeric'}):'';
  const maxActions=Math.max(...d.units.map(u=>u.total_meaningful_actions),1);
  let html=`<div style="font-size:var(--fs-xs);color:var(--muted);margin-bottom:8px">${esc(since)} · ${d.active_units}/${d.total_units} squadrons active</div>`;
  html+=`<div class="tw"><table><thead><tr>
    <th>Squadron</th><th style="text-align:center">Active Accounts</th><th style="text-align:center">Total Actions</th>
    <th style="text-align:center">Sessions Scheduled</th><th style="text-align:center">Outcomes Recorded</th>
    <th style="text-align:center">Programs Published</th><th style="text-align:center">Facilitators Managed</th><th>Last Activity</th>
  </tr></thead><tbody>`;
  for(const u of d.units){
    const w=maxActions?Math.round(u.total_meaningful_actions/maxActions*100):0;
    const last=u.last_activity?fmtD(u.last_activity.substring(0,10),{day:'numeric',month:'short',year:'2-digit'}):'—';
    const active=u.total_meaningful_actions>0;
    html+=`<tr>
      <td style="font-weight:600">${esc(u.code)}<span style="font-weight:400;color:var(--muted);font-size:var(--fs-xs)"> ${esc(u.name)}</span></td>
      <td style="text-align:center">${u.active_users}</td>
      <td style="text-align:center">
        <div style="display:flex;align-items:center;gap:6px">
          <div style="flex:1;height:6px;background:var(--border);border-radius:3px"><div style="height:100%;width:${w}%;background:${active?'var(--blue)':'var(--lgrey)'};border-radius:3px"></div></div>
          <span style="min-width:24px;font-size:var(--fs-xs)">${u.total_meaningful_actions}</span>
        </div>
      </td>
      <td style="text-align:center">${u.sessions_scheduled}</td>
      <td style="text-align:center">${u.outcomes_recorded}</td>
      <td style="text-align:center">${u.programs_published}</td>
      <td style="text-align:center">${u.facilitators_maintained}</td>
      <td style="font-size:var(--fs-xs);color:${active?'var(--text)':'var(--muted)'}">${last}</td>
    </tr>`;
  }
  html+='</tbody></table></div>';
  container.innerHTML=html;
}

function renderWing(){
  const host=document.getElementById('wing-dash'); if(!host)return;
  const rows=(S.wing&&S.wing.squadrons)||[];
  const tot=k=>rows.reduce((a,r)=>a+(+r[k]||0),0);
  const sessions=tot('sessions'), delivered=tot('delivered'), nd=tot('not_delivered'), nights=tot('nights');
  const delPct=sessions?Math.round(delivered/sessions*100):0;
  const avgCov=rows.length?Math.round(rows.reduce((a,r)=>a+(+r.coverage_pct||0),0)/rows.length):0;
  const atRisk=rows.filter(r=>r.no_published_plan||r.no_future_plan||(+r.not_delivered||0)>2).length;
  const canProxy=['wing_admin','national_admin','system_admin'].includes(S.role);
  const reads=rows.map(r=>r.readiness).filter(v=>v!=null&&v!==undefined).sort((a,b)=>a-b);
  const medRead=reads.length?(reads.length%2?reads[(reads.length-1)/2]:Math.round((reads[reads.length/2-1]+reads[reads.length/2])/2)):null;
  const highRisk=rows.filter(r=>r.no_published_plan||r.no_future_plan||(+r.not_delivered||0)>2||(+r.coverage_pct||0)<34).length;
  const noData=rows.filter(r=>(+r.nights||0)===0||(+r.sessions||0)===0).length;
  let html=`<div class="ph"><h2 class="ph-title">${S.scopeName||'Wing'} — Training Assurance</h2><div class="ph-sub">Oversight across ${rows.length} squadrons</div></div>`;
  html+=`<div class="stats-grid">
    <div class="stat"><div class="sval">${rows.length}</div><div class="slbl">Total SQNs</div></div>
    <div class="stat ${medRead==null?'':(medRead>=67?'s-ok':medRead>=34?'s-warn':'s-red')}"><div class="sval">${medRead==null?'—':medRead}</div><div class="slbl">Median Readiness</div></div>
    <div class="stat ${delPct>=67?'s-ok':delPct>=34?'s-warn':'s-red'}"><div class="sval">${delPct}%</div><div class="slbl">Delivery Completion</div></div>
    <div class="stat ${highRisk?'s-red':'s-ok'}"><div class="sval">${highRisk}</div><div class="slbl">High-Risk SQNs</div></div>
    <div class="stat ${noData?'s-warn':'s-ok'}"><div class="sval">${noData}</div><div class="slbl">No-Data SQNs</div></div>
    <div class="stat ${nd?'s-red':'s-ok'}"><div class="sval">${nd}</div><div class="slbl">Not Delivered</div></div>
  </div>`;
  // Comparison table
  html+=`<div class="card"><h2 class="ctitle">Squadron Comparison</h2><div class="tw"><table>
    <thead><tr><th>Squadron</th><th>Parade Day</th><th style="text-align:center">Nights</th><th style="text-align:center">Pub.</th><th style="text-align:center">Sessions</th><th>Delivered</th><th>Coverage</th><th style="text-align:center">Not Del.</th><th style="text-align:center">Readiness</th><th>Status</th>${canProxy?'<th class="no-print"></th>':''}</tr></thead><tbody>`;
  rows.forEach(r=>{
    html+=`<tr class="drow" onclick="wingDrill('${_jsAttr(r.squadron_id)}')">
      <td style="font-weight:800">${esc(r.short_name||r.code)}</td>
      <td style="font-size:var(--fs-xs)">${esc(r.parade_day||'—')}</td>
      <td style="text-align:center;font-weight:700">${r.nights||0}</td>
      <td style="text-align:center">${r.published||0}</td>
      <td style="text-align:center;font-weight:700">${r.sessions||0}</td>
      <td>${miniBar(r.sessions?Math.round((r.delivered||0)/r.sessions*100):0)}</td>
      <td>${miniBar(r.coverage_pct||0)}</td>
      <td style="text-align:center"><span class="badge ${(+r.not_delivered||0)===0?'b-ok':(+r.not_delivered<=2?'b-amber':'b-red')}">${r.not_delivered||0}</span></td>
      <td style="text-align:center;font-weight:700">${readinessDot(r.readiness)}</td>
      <td>${statusBadge(r)}</td>
      ${canProxy?`<td class="no-print"><button class="btn btn-out btn-sm" onclick="event.stopPropagation();enterMode('${_jsAttr(r.squadron_id)}','${_jsAttr(r.short_name||r.code)}')">Proxy</button></td>`:''}
    </tr>`;
  });
  html+=`</tbody></table></div></div>`;
  html+=`<div class="drill-panel" id="wing-drill"></div>`;
  // Phase-by-phase curriculum coverage and facilitator subject-area balance --
  // this data was already being fetched (S.wingPhase/S.cap, loadData()) but
  // never rendered anywhere; this card previously just pointed at page names
  // ("Curriculum Coverage", "Training Balance") that don't exist in this app.
  // Stage 9, 2026-08-05.
  if(S.wingPhase&&S.wingPhase.phases&&S.wingPhase.phases.length){
    const wp=S.wingPhase;
    html+=`<div class="card"><h2 class="ctitle">Curriculum Coverage — by Phase</h2><div class="tw"><table>
      <thead><tr><th>Squadron</th>${wp.phases.map(ph=>`<th style="text-align:center;font-size:var(--fs-2xs)">${esc(PH_S[ph]||ph)}</th>`).join('')}</tr></thead><tbody>`+
      wp.squadrons.map(s=>`<tr><td style="font-weight:800">${esc(s.short_name||'')}</td>${wp.phases.map(ph=>{
        const pct=(s.phase_pct&&s.phase_pct[ph])||0;
        return `<td style="text-align:center"><span class="badge ${pct>=67?'b-ok':pct>=34?'b-amber':pct?'b-red':''}">${pct}%</span></td>`;
      }).join('')}</tr>`).join('')+
      `</tbody></table></div></div>`;
  }
  if(S.cap&&S.cap.squadrons&&S.cap.squadrons.length){
    const cp=S.cap;
    html+=`<div class="card"><h2 class="ctitle">Training Balance — Facilitator Subject-Area Coverage</h2><div class="tw"><table>
      <thead><tr><th>Squadron</th>${SUBJECTS.map(s=>`<th style="text-align:center;font-size:var(--fs-2xs)" title="${esc(s.label)}">${s.emoji}</th>`).join('')}</tr></thead><tbody>`+
      cp.squadrons.map(s=>`<tr><td style="font-weight:800">${esc(s.short_name||'')}</td>${SUBJECTS.map(su=>{
        const n=(s.subject_facilitators&&s.subject_facilitators[su.key])||0;
        return `<td style="text-align:center">${n===0?'<span class="badge b-red">0</span>':`<span class="badge b-ok">${n}</span>`}</td>`;
      }).join('')}</tr>`).join('')+
      `</tbody></table></div><div style="font-size:var(--fs-2xs);color:var(--muted);margin-top:8px">Red = no facilitator in this Squadron tagged for that subject area.</div></div>`;
  }
  // T2-04 — Cancellation trend
  if(S.wingCancel){
    const wc=S.wingCancel;
    const hasData=wc.squadrons&&wc.squadrons.length&&(wc.total_cancelled_sessions+wc.total_cancelled_nights)>0;
    html+=`<div class="card"><h2 class="ctitle">Cancellation Trend${wc.total_cancelled_sessions||wc.total_cancelled_nights?` — <span class="badge b-amber">${wc.total_cancelled_sessions} cancelled sessions · ${wc.total_cancelled_nights} stand-downs</span>`:' — No cancellations this period'}</h2>`;
    if(hasData){
      html+=`<div class="tw"><table><thead><tr><th>Squadron</th><th style="text-align:center">Cancelled sessions</th><th style="text-align:center">Stand-downs</th><th>Top reason</th></tr></thead><tbody>`;
      wc.squadrons.forEach(s=>{
        if(!s.cancelled_sessions&&!s.cancelled_nights)return;
        const top=s.reasons&&s.reasons[0];
        html+=`<tr><td style="font-weight:800">${esc(s.short_name||s.code)}</td>
          <td style="text-align:center"><span class="badge ${s.cancelled_sessions?'b-amber':'b-ok'}">${s.cancelled_sessions}</span></td>
          <td style="text-align:center"><span class="badge ${s.cancelled_nights?'b-red':'b-ok'}">${s.cancelled_nights}</span></td>
          <td style="font-size:var(--fs-xs)">${top?esc(top.reason+' (×'+top.count+')'):'—'}</td></tr>`;
      });
      html+=`</tbody></table></div>`;
    } else {
      html+=`<div style="color:var(--ok);font-size:var(--fs-sm);padding:8px 0">No cancelled sessions or stand-downs recorded. Programme is on track.</div>`;
    }
    html+=`</div>`;
  }
  // T2-05 — Wing not-delivered
  if(S.wingNdel){
    const wn=S.wingNdel;
    const hasData=wn.squadrons&&wn.squadrons.length>0;
    html+=`<div class="card"><h2 class="ctitle">Not-Delivered Sessions — Wing Summary${wn.total_not_delivered?` <span class="badge b-red">${wn.total_not_delivered} total</span>`:''}</h2>`;
    if(hasData){
      html+=`<div class="tw"><table><thead><tr><th>Squadron</th><th style="text-align:center">Count</th><th>Sample</th></tr></thead><tbody>`;
      wn.squadrons.forEach(s=>{
        const sample=s.sessions&&s.sessions[0];
        const sampleText=sample?(sample.curriculum_code_at_time||'—')+(sample.not_delivered_reason?' — '+sample.not_delivered_reason:''):'—';
        html+=`<tr><td style="font-weight:800">${esc(s.short_name||s.code)}</td>
          <td style="text-align:center"><span class="badge b-red">${s.not_delivered_count}</span></td>
          <td style="font-size:var(--fs-xs);color:var(--text-2)">${esc(sampleText)}${s.sessions&&s.sessions.length>1?` <span class="muted">(+${s.sessions.length-1} more)</span>`:''}</td></tr>`;
      });
      html+=`</tbody></table></div><div style="font-size:var(--fs-2xs);color:var(--muted);margin-top:6px">Enter Proxy Mode for a squadron to review and resolve not-delivered sessions.</div>`;
    } else {
      html+=`<div style="color:var(--ok);font-size:var(--fs-sm);padding:8px 0">No not-delivered sessions recorded across the Wing.</div>`;
    }
    html+=`</div>`;
  }
  host.innerHTML=html;
}
function wingDrill(sid){
  const r=((S.wing&&S.wing.squadrons)||[]).find(x=>x.squadron_id===sid); const p=document.getElementById('wing-drill'); if(!r||!p)return;
  p.className='drill-panel show';
  p.innerHTML=`<div class="drill-hdr"><div class="drill-title">${esc(r.short_name||r.code)} — detail</div><button class="modal-x" aria-label="Close" onclick="document.getElementById('wing-drill').className='drill-panel'">×</button></div>
    <div class="stats-grid" style="margin:0">
      <div class="stat"><div class="sval">${r.nights||0}</div><div class="slbl">Nights (${r.published||0} published)</div></div>
      <div class="stat"><div class="sval">${r.sessions||0}</div><div class="slbl">Sessions</div></div>
      <div class="stat ${(+r.coverage_pct>=67)?'s-ok':'s-warn'}"><div class="sval">${r.coverage_pct||0}%</div><div class="slbl">Coverage</div></div>
      <div class="stat ${(+r.not_delivered)?'s-red':'s-ok'}"><div class="sval">${r.not_delivered||0}</div><div class="slbl">Not Delivered</div></div>
    </div>
    <div style="font-size:var(--fs-xs);color:var(--muted);margin-top:10px">Read-only oversight view. ${S.role==='wing_admin'?'To change this squadron, enter Proxy Mode using the Proxy button on the row.':'Wing viewers are read-only.'}</div>`;
}

// ═══ NATIONAL DASHBOARD (backend: /api/national/overview + reports/national-overview) ═══
function renderNational(){
  const host=document.getElementById('national-dash'); if(!host)return;
  const wings=(S.nationalReport&&S.nationalReport.wings)||[];
  const tot=k=>wings.reduce((a,w)=>a+(+w[k]||0),0);
  const sqs=tot('squadrons'), sessions=tot('sessions'), delivered=tot('delivered'), nd=tot('not_delivered');
  const delPct=sessions?Math.round(delivered/sessions*100):0;
  const avgCov=wings.length?Math.round(wings.reduce((a,w)=>a+(+w.coverage_pct||0),0)/wings.length):0;
  const atRisk=wings.filter(w=>(+w.not_delivered||0)>2||(+w.coverage_pct||0)<34).length;
  let html=`<div class="ph"><h2 class="ph-title">National HQ — Assurance Overview</h2><div class="ph-sub">${wings.length} wings · ${sqs} squadrons</div></div>`;
  html+=`<div class="stats-grid">
    <div class="stat s-purple"><div class="sval">${wings.length}</div><div class="slbl">Wings</div></div>
    <div class="stat"><div class="sval">${sqs}</div><div class="slbl">Squadrons</div></div>
    <div class="stat ${delPct>=67?'s-ok':delPct>=34?'s-warn':'s-red'}"><div class="sval">${delPct}%</div><div class="slbl">Delivered (${delivered}/${sessions})</div></div>
    <div class="stat ${nd?'s-red':'s-ok'}"><div class="sval">${nd}</div><div class="slbl">Not Delivered</div></div>
    <div class="stat ${avgCov>=67?'s-ok':avgCov>=34?'s-warn':'s-red'}"><div class="sval">${avgCov}%</div><div class="slbl">Avg Coverage</div></div>
    <div class="stat ${atRisk?'s-red':'s-ok'}"><div class="sval">${atRisk}</div><div class="slbl">Wings Needing Attention</div></div>
  </div>`;
  html+=`<div class="card"><h2 class="ctitle">Wing Comparison</h2><div class="tw"><table>
    <thead><tr><th>Wing</th><th style="text-align:center">Squadrons</th><th style="text-align:center">Sessions</th><th>Delivered</th><th>Coverage</th><th style="text-align:center">Not Del.</th><th>Status</th></tr></thead><tbody>`;
  wings.forEach(w=>{
    const dp=w.sessions?Math.round((w.delivered||0)/w.sessions*100):0;
    html+=`<tr class="drow" onclick="nationalDrill('${w.wing_id}')">
      <td style="font-weight:800">${esc(w.name||w.code)}</td>
      <td style="text-align:center;font-weight:700">${w.squadrons||0}</td>
      <td style="text-align:center">${w.sessions||0}</td>
      <td>${miniBar(dp)}</td><td>${miniBar(w.coverage_pct||0)}</td>
      <td style="text-align:center"><span class="badge ${(+w.not_delivered||0)===0?'b-ok':(+w.not_delivered<=2?'b-amber':'b-red')}">${w.not_delivered||0}</span></td>
      <td>${(+w.coverage_pct||0)>=67?'<span class="badge b-ok">On track</span>':(+w.coverage_pct||0)>=34?'<span class="badge b-amber">Monitor</span>':'<span class="badge b-red">At risk</span>'}</td>
    </tr>`;
  });
  html+=`</tbody></table></div></div><div class="drill-panel" id="national-drill"></div>`;
  // National capability gap summary (from national-capability)
  if(S.natCap&&S.natCap.wings){
    html+=`<div class="card"><h2 class="ctitle">National Capability — SQNs with no facilitator coverage</h2><div class="tw"><table>
      <thead><tr><th>Wing</th>${SUBJECTS.map(s=>`<th style="text-align:center;font-size:var(--fs-2xs)" title="${s.label}">${s.label}</th>`).join('')}</tr></thead><tbody>`+
      S.natCap.wings.map(w=>{const nn=w.subject_none_sqns||{};return `<tr><td style="font-weight:800">${esc(w.name||w.code)}</td>${SUBJECTS.map(s=>`<td style="text-align:center">${nn[s.key]?`<span class="badge b-red">${nn[s.key]}</span>`:'<span class="badge b-ok">&#10003;</span>'}</td>`).join('')}</tr>`;}).join('')+
      `</tbody></table></div><div style="font-size:var(--fs-2xs);color:var(--muted);margin-top:8px">Red = number of SQNs in that Wing with no facilitator tagged in the subject. Refer to Facilitator Load and Training Balance for detail.</div></div>`;
  }
  host.innerHTML=html;
}
function nationalDrill(wid){
  const w=((S.nationalReport&&S.nationalReport.wings)||[]).find(x=>x.wing_id===wid);
  const sqs=(S.squadrons||[]).filter(x=>x.wing_id===wid);
  const p=document.getElementById('national-drill'); if(!p)return; p.className='drill-panel show';
  p.innerHTML=`<div class="drill-hdr"><div class="drill-title">${esc(w?(w.name||w.code):'Wing')} — squadrons</div><button class="modal-x" aria-label="Close" onclick="document.getElementById('national-drill').className='drill-panel'">×</button></div>
    <div class="tw"><table><thead><tr><th>Squadron</th><th>Parade Day</th><th>Address</th></tr></thead><tbody>
    ${sqs.length?sqs.map(s=>`<tr><td style="font-weight:800">${esc(s.short_name||s.code)}</td><td>${esc(s.default_parade_day||'—')}</td><td style="font-size:var(--fs-xs)">${esc((s.address||'').split(',')[0])}</td></tr>`).join(''):'<tr><td colspan="3" style="color:var(--muted)">No squadrons returned</td></tr>'}
    </tbody></table></div>
    <div style="font-size:var(--fs-xs);color:var(--muted);margin-top:10px">Read-only national oversight. ${['national_admin','system_admin'].includes(S.role)?'Deeper squadron changes require Delegated Intervention Mode, where permitted.':'National viewers are read-only.'}</div>`;
}

// ═══ AUDIT LOG ═══
function renderAudit(){
  const tb=document.getElementById('audit-tbody'); if(!tb)return;
  const rows=S.audit||[];
  tb.innerHTML=rows.length?rows.map(a=>`<tr>
    <td style="font-size:var(--fs-xs);white-space:nowrap">${(a.timestamp||'').replace('T',' ').slice(0,16)}</td>
    <td><span class="badge b-blue">${esc(a.role||'—')}</span></td>
    <td style="font-weight:700">${esc(a.action||'')}</td>
    <td style="font-size:var(--fs-xs)">${esc(a.object_type||'')}</td>
    <td style="font-size:var(--fs-xs);color:var(--muted)">${esc(a.reason||'')}</td></tr>`).join('')
    :`<tr><td colspan="5" style="color:var(--muted)">${S.auditDenied
        ? 'Your role cannot read the audit log. Ask a Wing or National administrator if you need this.'
        : 'No audit entries.'}</td></tr>`;
}

// ═══ SUBJECT AREAS (backend `element` mapped to the six training categories) ═══
const SUBJECTS=[
  {key:'service', label:'Service Knowledge',                    emoji:'📚', cls:'b-blue',   els:['SQN_Affairs','Service']},
  {key:'drill',   label:'Drill and Ceremonial',                 emoji:'🥾', cls:'b-red',    els:['Drill']},
  {key:'field',   label:'Field Skills',                         emoji:'🏕️', cls:'b-ok',     els:['Field','Fieldcraft']},
  {key:'lead',    label:'Personal Development and Leadership',  emoji:'⭐', cls:'b-purple', els:['Personal_Dev','Leadership']},
  {key:'comm',    label:'Community Engagement',                 emoji:'🤝', cls:'b-amber',  els:['Service_Community','SFA']},
  {key:'stem',    label:'Aviation and Air Power',               emoji:'🛩️', cls:'b-teal',   els:['Air_Space','STEM']},
];
function subjectOf(el){ if(!el)return null; const m=SUBJECTS.find(s=>s.els.some(e=>String(el).toLowerCase().includes(e.toLowerCase().split('_')[0]))); return m?m.key:null; }
