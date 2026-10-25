"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const NS = "http://www.w3.org/2000/svg";
  const palette = ["var(--spec)", "var(--pass)", "var(--accent)", "var(--purple)", "var(--muted)"];
  const workKeys = ["spec", "context", "production", "tests", "tooling"];
  const workColors = [palette[0], palette[3], "var(--code)", palette[1], palette[4]];
  let data, selected = 0, timer = null, resizeTimer;
  const fmt = (v, digits=1) => v == null || !Number.isFinite(v) ? "—" : Number(v).toLocaleString(undefined, {maximumFractionDigits:digits});
  const pct = v => v == null ? "—" : `${fmt(v*100)}%`;
  const finite = v => v !== null && v !== undefined && Number.isFinite(v);
  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[ch]));
  const label = row => row.pr ? `#${row.pr}` : row.sha.slice(0,7);
  function svgElement(tag, attrs={}, parent, text) {
    const el = document.createElementNS(NS, tag);
    for (const [k,v] of Object.entries(attrs)) el.setAttribute(k, v);
    if (text !== undefined) el.textContent = text;
    if (parent) parent.appendChild(el);
    return el;
  }
  function empty(id, message="No recorded data at this snapshot.") { $(id).innerHTML = `<div class="empty">${esc(message)}</div>`; }
  function tooltip(ev, lines) {
    const box = $("tooltip");
    box.replaceChildren();
    for (const line of lines) { const d=document.createElement("div"); d.textContent=line; box.appendChild(d); }
    box.hidden=false;
    box.style.left=`${Math.max(8,Math.min(innerWidth-box.offsetWidth-12,ev.clientX+16))}px`;
    box.style.top=`${Math.max(8,Math.min(innerHeight-box.offsetHeight-12,ev.clientY+16))}px`;
  }
  const hide = () => { $("tooltip").hidden=true; };
  function legend(container, series) {
    const el=document.createElement("div");el.className="legend";
    for (const s of series) {
      const item=document.createElement("span"), swatch=document.createElement("i");
      swatch.style.background=s.color;item.append(swatch,document.createTextNode(s.name));el.appendChild(item);
    }
    container.appendChild(el);
  }
  function canvas(id, height=245) {
    const container=$(id);container.replaceChildren();
    const width=Math.max(260,container.getBoundingClientRect().width);
    const svg=svgElement("svg",{class:"plot",viewBox:`0 0 ${width} ${height}`,role:"img","aria-label":container.parentElement.querySelector("h3")?.textContent || id},container);
    return {container,svg,width,height};
  }
  function lines(id, rows, series, unit, options={}) {
    const all=series.flatMap(s=>rows.map(s.get)).filter(finite);
    if (!all.length) return empty(id);
    const {container,svg,width,height}=canvas(id);
    const left=54,right=12,top=16,bottom=43, w=width-left-right,h=height-top-bottom;
    const max=Math.max(...all, ...(options.band ? rows.flatMap(r=>r.band||[]) : []), options.ceiling||0);
    const min=Math.min(0,...all);
    const span=max-min || 1;
    const x=i=>left+i*w/Math.max(rows.length-1,1), y=v=>top+h-(v-min)/span*h;
    for(let t=0;t<=4;t++) {
      const value=min+span*t/4, yy=y(value);
      svgElement("line",{x1:left,x2:width-right,y1:yy,y2:yy,class:"gridline"},svg);
      svgElement("text",{x:left-8,y:yy+4,"text-anchor":"end"},svg,fmt(value,max>100?0:1));
    }
    const indices=[...new Set([0,Math.round((rows.length-1)/2),rows.length-1])];
    indices.forEach(i=>svgElement("text",{x:x(i),y:height-25,"text-anchor":i===0?"start":i===rows.length-1?"end":"middle"},svg,label(rows[i])));
    svgElement("text",{x:left,y:11,class:"axis-title"},svg,unit);
    svgElement("text",{x:left+w/2,y:height-4,"text-anchor":"middle",class:"axis-title"},svg,"Main-line history →");
    if(options.band) {
      let segment=[];
      function flush() {
        if(segment.length) {
          const upper=segment.map(i=>`${x(i)},${y(rows[i].band[1])}`).join(" L");
          const lower=segment.slice().reverse().map(i=>`${x(i)},${y(rows[i].band[0])}`).join(" L");
          svgElement("path",{d:`M${upper} L${lower} Z`,fill:"var(--band)"},svg);
        }
        segment=[];
      }
      rows.forEach((r,i)=>{if(r.band)segment.push(i);else flush();});flush();
    }
    for(const s of series) {
      let segment=[];
      const flush=()=>{if(segment.length)svgElement("path",{d:segment.map((p,i)=>`${i?"L":"M"}${x(p[0])},${y(p[1])}`).join(" "),fill:"none",stroke:s.color,"stroke-width":2,"stroke-dasharray":s.dashed?"5 4":"none"},svg);segment=[];};
      rows.forEach((r,i)=>{const v=s.get(r);if(finite(v))segment.push([i,v]);else flush();});flush();
      rows.forEach((r,i)=>{if(finite(s.get(r)) && (rows.length===1||i===selected))svgElement("circle",{cx:x(i),cy:y(s.get(r)),r:3,fill:s.color},svg);});
    }
    if(selected<rows.length)svgElement("line",{x1:x(selected),x2:x(selected),y1:top,y2:top+h,class:"selected"},svg);
    const hit=svgElement("rect",{x:left,y:top,width:w,height:h,fill:"transparent"},svg);
    function index(ev){const rect=svg.getBoundingClientRect();return Math.max(0,Math.min(rows.length-1,Math.round(((ev.clientX-rect.left)*width/rect.width-left)/w*(rows.length-1))));}
    hit.addEventListener("pointermove",ev=>{const i=index(ev),r=rows[i];tooltip(ev,[`${label(r)} · ${r.date}`,r.title,...series.map(s=>`${s.name}: ${fmt(s.get(r))} ${unit}`)]);});
    hit.addEventListener("pointerleave",hide);
    hit.addEventListener("click",ev=>{choose(index(ev));hide();});
    legend(container,series);
  }
  function bars(id, items, keys, unit="items", horizontal=false) {
    if(!items.length) return empty(id);
    const height=horizontal?Math.max(200,items.length*36+55):245;
    const {container,svg,width}=canvas(id,height);
    const left=horizontal?Math.min(145,width*.37):48,right=horizontal?54:10,top=15,bottom=40,w=width-left-right,h=height-top-bottom;
    const total=item=>keys.reduce((sum,key)=>sum+(item[key.key]||0),0),maximum=Math.max(1,...items.map(total));
    if(horizontal) {
      items.forEach((item,i)=>{
        const yy=top+i*h/items.length, bh=Math.min(22,h/items.length-7);let xx=left;
        const text=svgElement("text",{x:left-9,y:yy+bh/2+4,"text-anchor":"end"},svg,item.name.length>23?item.name.slice(0,21)+"…":item.name);
        svgElement("title",{},text,item.name);
        keys.forEach(key=>{const value=item[key.key]||0,bw=value/maximum*w;if(!bw)return;const rect=svgElement("rect",{x:xx,y:yy,width:bw,height:bh,fill:key.color},svg);svgElement("title",{},rect,`${item.name} · ${key.name}: ${value} ${unit}`);xx+=bw;});
        svgElement("text",{x:xx+6,y:yy+bh/2+4},svg,fmt(total(item),0));
      });
      [0,maximum/2,maximum].forEach(v=>svgElement("text",{x:left+v/maximum*w,y:height-20,"text-anchor":v===0?"start":v===maximum?"end":"middle"},svg,fmt(v,0)));
    } else {
      for(let t=0;t<=3;t++){const value=maximum*t/3,yy=top+h-value/maximum*h;svgElement("line",{x1:left,x2:width-right,y1:yy,y2:yy,class:"gridline"},svg);svgElement("text",{x:left-7,y:yy+4,"text-anchor":"end"},svg,fmt(value,0));}
      items.forEach((item,i)=>{const bw=w/items.length,xx=left+i*bw;let baseline=top+h;
        keys.forEach(key=>{const value=item[key.key]||0,bh=value/maximum*h;if(!bh)return;svgElement("rect",{x:xx+1,y:baseline-bh,width:Math.max(.6,bw-2),height:bh,fill:key.color},svg);baseline-=bh;});
        const hit=svgElement("rect",{x:xx,y:top,width:bw,height:h,fill:"transparent"},svg);
        hit.addEventListener("pointermove",ev=>tooltip(ev,[item.name,...keys.map(k=>`${k.name}: ${fmt(item[k.key]||0,0)} ${unit}`)]));hit.addEventListener("pointerleave",hide);
        if(item.index!==undefined)hit.addEventListener("click",()=>choose(item.index));
      });
      [0,Math.floor((items.length-1)/2),items.length-1].filter((v,i,a)=>a.indexOf(v)===i).forEach(i=>svgElement("text",{x:left+(i+.5)*w/items.length,y:height-20,"text-anchor":i===0?"start":i===items.length-1?"end":"middle"},svg,items[i].short||items[i].name));
    }
    svgElement("text",{x:left+w/2,y:height-3,"text-anchor":"middle",class:"axis-title"},svg,unit);
    if(keys.length>1)legend(container,keys);
  }
  function table(id, headings, rows) {
    if(!rows.length)return empty(id);
    $(id).innerHTML=`<table><thead><tr>${headings.map(h=>`<th scope="col">${esc(h)}</th>`).join("")}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(c=>`<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  }
  function heatmap(rows) {
    const paths=[...new Set(rows.flatMap(r=>Object.keys(r.spec_edits)))].sort();
    if(!paths.length)return empty("heatmap");
    const container=$("heatmap");container.replaceChildren();
    const width=Math.max(container.clientWidth,720),left=260,cw=(width-left-10)/Math.max(1,rows.length),rh=19;
    const svg=svgElement("svg",{viewBox:`0 0 ${width} ${paths.length*rh+35}`,width,height:paths.length*rh+35,role:"img","aria-label":"Spec file edits by first-parent commit"},container);
    const max=Math.max(1,...rows.flatMap(r=>Object.values(r.spec_edits)));
    paths.forEach((path,j)=>{const t=svgElement("text",{x:left-10,y:j*rh+13,"text-anchor":"end",fill:"var(--secondary)","font-size":10},svg,path.length>42?"…"+path.slice(-41):path);svgElement("title",{},t,path);
      rows.forEach((row,i)=>{const count=row.spec_edits[path]||0;const rect=svgElement("rect",{x:left+i*cw,y:j*rh,width:Math.max(.5,cw-1),height:rh-2,fill:count?"var(--spec)":"var(--line)",opacity:count?.25+.75*Math.log1p(count)/Math.log1p(max):.25},svg);svgElement("title",{},rect,`${label(row)} · ${path}: ${count} changed lines`);rect.addEventListener("pointermove",ev=>tooltip(ev,[label(row),path,`${count} changed lines`]));rect.addEventListener("pointerleave",hide);rect.addEventListener("click",()=>choose(i));});
    });
    svgElement("text",{x:left,y:paths.length*rh+20,fill:"var(--secondary)","font-size":11},svg,`${label(rows[0])} → ${label(rows.at(-1))} · Main-line history`);
  }
  const kilo=n=>n>=1e6?`${fmt(n/1e6,2)}M`:n>=1e3?`${fmt(n/1e3,0)}k`:fmt(n,0);
  function drawUsage(u) {
    const U=u.rows||[];
    if(!U.length){["usage-models","usage-days","usage-branches"].forEach(id=>empty(id,u.status==="disabled"?"Token logs skipped (--no-usage).":`No Claude Code or Codex session logs found for this repository (${u.status}).`));return;}
    const sum=(rows,k)=>rows.reduce((n,r)=>n+r[k],0),context=rows=>sum(rows,"input")+sum(rows,"cache_write")+sum(rows,"cache_read");
    const perReply=rows=>kilo(Math.round(context(rows)/Math.max(1,sum(rows,"replies"))));
    const models=[...new Set(U.map(r=>r.model))].sort((a,b)=>sum(U.filter(r=>r.model===b),"output")-sum(U.filter(r=>r.model===a),"output"));
    const colors=[palette[0],palette[2],palette[3],palette[1],"var(--code)",palette[4]],keys=models.map((m,i)=>({key:m,name:m,color:colors[i%colors.length]}));
    const of=m=>U.filter(r=>r.model===m);
    table("usage-models",["Model","Tool","Replies","Output","Context read","Cache read","Context per reply","Share of output"],[...models.map(m=>[`<span class="mono">${esc(m)}</span>`,esc([...new Set(of(m).map(r=>r.tool))].join(", ")),fmt(sum(of(m),"replies"),0),kilo(sum(of(m),"output")),kilo(context(of(m))),kilo(sum(of(m),"cache_read")),perReply(of(m)),pct(sum(of(m),"output")/Math.max(1,sum(U,"output")))]),["<b>All</b>","",fmt(sum(U,"replies"),0),`<b>${kilo(sum(U,"output"))}</b>`,`<b>${kilo(context(U))}</b>`,kilo(sum(U,"cache_read")),perReply(U),"100%"]]);
    const dates=[...new Set(U.map(r=>r.date))].sort();
    bars("usage-days",dates.map(d=>({name:`${d} · ${perReply(U.filter(r=>r.date===d))} context per reply`,short:d.slice(5),...Object.fromEntries(models.map(m=>[m,sum(U.filter(r=>r.date===d&&r.model===m),"output")]))})),keys,"output tokens");
    const branches=[...new Set(U.map(r=>r.branch))].map(b=>({b,rows:U.filter(r=>r.branch===b)})).sort((a,b)=>sum(b.rows,"output")-sum(a.rows,"output"));
    table("usage-branches",["Branch","Replies","Output","Context read","Context per reply",...models],branches.map(({b,rows})=>[`<span class="mono">${esc(b||"(none)")}</span>`,fmt(sum(rows,"replies"),0),kilo(sum(rows,"output")),kilo(context(rows)),perReply(rows),...models.map(m=>{const v=sum(rows.filter(r=>r.model===m),"output");return v?kilo(v):"–";})]));
  }
  function render() {
    const rows=data.rows,r=rows[selected],timeline=rows; if(!r)return;
    $("history").value=selected;
    $("selection").textContent=`${selected+1} / ${rows.length} · ${r.date} · ${label(r)} · ${r.title}`;
    const closed=r.issues.closed,total=closed+r.issues.open,merged=r.changes.reduce((n,c)=>n+c.done.length,0),planned=r.changes.reduce((n,c)=>n+c.steps.length,0);
    const cards=[[`${closed} / ${total}`,"Tracked O-items closed",total?`${pct(closed/total)} by count, not effort`:"No structured O-items yet"],[`${merged} / ${planned}`,"Change steps merged",`${r.changes.filter(c=>!c.next).length} of ${r.changes.length} changes complete`],[`${r.links.linked} / ${r.links.declared}`,"Scenario source links",`${r.links.manual} manual · ${r.locked} locked test entries`],[r.note.confirmed?"Confirmed":r.note.status==="recorded"?"Recorded":r.note.status==="missing"?"No note":"Malformed","Selected commit’s CI note",r.note.result?`${r.note.result} · ${r.note.confirmed?"GitHub checked":"not freshly confirmed"}`:"No result available"]];
    $("stats").innerHTML=cards.map(([value,name,detail])=>`<div class="stat"><div class="value">${esc(value)}</div><div class="label">${esc(name)}</div><small>${esc(detail)}</small></div>`).join("");
    const active=r.changes.filter(c=>c.next),current=active[0];
    $("current").innerHTML=current?`<h3>${esc(current.name)} <span class="mono">/ ${esc(current.next)}</span></h3><p>${esc(current.steps.find(s=>s.name===current.next)?.goal)} · ${esc(current.rigor)} rigor</p>`:`<h3>${r.changes.length?"All declared changes complete":"Before structured changes"}</h3><p>The roadmap and historical charts below remain available.</p>`;
    $("change-lanes").innerHTML=r.changes.map(c=>`<div class="lane"><div class="lane-label">${esc(c.name)}<small>${c.done.length}/${c.steps.length} merged · ${esc(c.rigor)}</small></div><div class="step-list">${c.steps.map(s=>`<span class="step ${c.done.includes(s.name)?"done":s.name===c.next?"next":""}" title="${esc(s.goal)}">${esc(s.name)}${c.done.includes(s.name)?" ✓":""}</span>`).join("")}</div></div>`).join("");
    lines("issues-chart",timeline,[{name:"Closed",color:palette[1],get:r=>r.issues.closed},{name:"Open",color:palette[2],get:r=>r.issues.open}],"O-items");
    const builds=[...new Set(r.issue_list.map(i=>i.build))].sort((a,b)=>(a??999)-(b??999)).map(build=>({name:build===null?"Change-owned":`Build ${build}`,closed:r.issue_list.filter(i=>i.build===build&&i.closed).length,open:r.issue_list.filter(i=>i.build===build&&!i.closed).length}));
    bars("roadmap-chart",builds,[{key:"closed",name:"Closed",color:palette[1]},{key:"open",name:"Open",color:palette[2]}],"O-items",true);
    bars("steps-chart",r.changes.map(c=>({name:c.name,merged:c.done.length,pending:c.steps.length-c.done.length})),[{key:"merged",name:"Merged",color:palette[1]},{key:"pending",name:"Pending",color:palette[4]}],"steps",true);
    const handoffs=r.changes.flatMap(c=>c.items.filter(i=>!i.closed).map(i=>({change:c.name,...i})));
    $("handoffs").innerHTML=handoffs.length?`<ul class="item-list">${handoffs.map(i=>`<li><span class="mono">${esc(i.change)}/${esc(i.step)} · ${esc(i.id)}</span><br>${esc(i.text)}</li>`).join("")}</ul>`:`<div class="empty">No open items in change steps.md files.</div>`;
    lines("gap-chart",timeline,[{name:"Spec–code gap",color:"var(--ink)",get:r=>r.gap},{name:"Chance mean",color:palette[0],dashed:true,get:r=>r.chance}],"degrees",{band:true});
    const delta=timeline.map((r,i)=>({...r,delta:i&&finite(r.gap)&&finite(timeline[i-1].gap)?r.gap-timeline[i-1].gap:null}));
    lines("delta-chart",delta,[{name:"Gap change",color:palette[2],get:r=>r.delta}],"degrees");
    lines("coverage-chart",timeline,[{name:"All-source coverage",color:palette[0],get:r=>r.coverage==null?null:r.coverage*100},{name:"Production coverage",color:palette[1],get:r=>r.production_coverage==null?null:r.production_coverage*100},{name:"Jaccard",color:palette[3],get:r=>r.jaccard==null?null:r.jaccard*100}],"%",{ceiling:100});
    lines("names-chart",timeline,[{name:"Retained",color:palette[3],get:r=>r.names_kept},{name:"Retired",color:palette[2],get:r=>r.names_retired}],"names");
    $("merge-detail").innerHTML=`<p class="mono">${esc(r.date)} · ${esc(r.sha.slice(0,12))}</p><div class="merge-title">${esc(r.title)}</div><dl class="readout"><div><dt>Gap</dt><dd>${fmt(r.gap)}°</dd></div><div><dt>Coverage</dt><dd>${pct(r.coverage)}</dd></div><div><dt>Changed lines</dt><dd>${fmt(Object.values(r.work).reduce((a,b)=>a+b,0),0)}</dd></div><div><dt>Merged steps</dt><dd>${esc(r.steps.join(", ")||"—")}</dd></div></dl>`;
    heatmap(timeline);
    bars("work-chart",timeline.map((r,index)=>({name:`${label(r)} · ${r.title}`,short:label(r),index,...r.work})),workKeys.map((key,i)=>({key,name:key,color:workColors[i]})),"changed lines");
    lines("cumulative-chart",timeline,workKeys.map((key,i)=>({name:key,color:workColors[i],get:r=>r.cumulative[key]||0})),"changed lines");
    lines("ratio-chart",timeline,[{name:"Tests / production",color:palette[1],get:r=>r.test_ratio}],"ratio");
    const days=new Map();rows.slice(0,selected+1).forEach(r=>days.set(r.date,(days.get(r.date)||0)+1));
    bars("activity-chart",[...days].map(([name,count])=>({name,count})),[{key:"count",name:"Commits",color:palette[0]}],"commits / date");
    const causes=new Map();r.defects.forEach(d=>causes.set(d.cause,(causes.get(d.cause)||0)+1));
    bars("defect-chart",[...causes].map(([name,count])=>({name,count})),[{key:"count",name:"Defects",color:palette[2]}],"defects",true);
    lines("links-chart",timeline,[{name:"Declared",color:palette[0],get:r=>r.links.declared},{name:"Linked",color:palette[1],get:r=>r.links.linked}],"scenarios");
    $("link-detail").textContent=`Unlinked: ${r.links.unlinked.join(", ")||"none"}. Unknown source links: ${r.links.unknown.join(", ")||"none"}.`;
    const states=["recorded pass","recorded fail","unconfirmed","missing"];
    lines("evidence-chart",timeline,states.map((name,i)=>({name,color:[palette[1],palette[2],palette[3],palette[4]][i],get:r=>r.evidence.filter(e=>e.state===name).length})),"scenario rows");
    const cell=entry=>entry?`<span class="${entry.result==="pass"?"pass":entry.result==="fail"?"fail":"unknown"}">${esc(entry.result||"unknown")}</span><br><code>${esc(String(entry.merged||entry.commit||"").slice(0,7))}</code>`:"—";
    table("evidence-table",["Change / scenario","Red","Green","Break","Ledger state"],r.evidence.map(e=>[`${esc(e.change)}<br><code>${esc(e.scenario)}</code>`,cell(e.red),cell(e.green),cell(e.break),esc(e.state)]));
    const noteStates=["recorded pass","recorded fail","missing","malformed"];
    bars("ci-chart",timeline.map((r,index)=>{const state=r.note.status==="recorded"?`recorded ${r.note.result}`:r.note.status;return {name:`${label(r)} · ${state}`,short:label(r),index,...Object.fromEntries(noteStates.map(s=>[s,state===s?1:0]))};}),noteStates.map((key,i)=>({key,name:key,color:[palette[1],palette[2],palette[4],palette[3]][i]})),"note presence (1 / commit)");
    $("ci-detail").textContent=`Selected note: ${r.note.status}${r.note.result?" / "+r.note.result:""} · ${r.note.confirmed?"latest run confirmed through GitHub":"not freshly confirmed"}. Per-test outcomes: ${r.note.outcomes||"unavailable"}.`;
    const claims=rows.slice(0,selected+1).flatMap(row=>(row.note.claims||[]).map(c=>({sha:row.sha,...c}))),counts=new Map();
    claims.forEach(c=>{const key=String(c.claim||c.label||"unknown").split(":")[0];counts.set(key,(counts.get(key)||0)+1);});
    bars("claims-chart",[...counts].map(([name,count])=>({name,count})),[{key:"count",name:"Claims",color:palette[3]}],"recorded claims",true);
    $("claims-detail").textContent=claims.length?claims.slice(-5).map(c=>`${c.claim||c.label} · ${c.by||"unknown applier"}`).join(" | "):"No claims recorded in available local notes.";
    const gh=data.github;
    const conclusions=new Map();
    (gh.runs||[]).forEach(run=>{const outcome=run.conclusion||run.status||"unknown";conclusions.set(outcome,(conclusions.get(outcome)||0)+1);});
    if(conclusions.size)bars("github-chart",[...conclusions].map(([name,count])=>({name,count})),[{key:"count",name:"Workflow runs",color:palette[0]}],"recent workflow runs",true);
    else empty("github-chart",gh.status==="disabled"?"Enable --github to load recent run outcomes.":"No recent runs available.");
    $("github-detail").innerHTML=gh.status==="disabled"?`<p>Offline mode. Restart with <code>--github</code> for recent runs, open PRs and latest-note confirmation.</p>`:`<p>GitHub: ${esc(gh.status)} · ${gh.saved?(gh.checked?`saved answer from ${esc(gh.checked)}, asking again…`:"asking…"):`checked ${esc(gh.checked)}`}</p><p>${gh.runs?.length||0} recent runs (bounded to 100); ${gh.open_prs?.length||0} open PRs.</p>${(gh.open_prs||[]).map(p=>`<div class="note-line">#${p.number} · ${esc(p.title)}</div>`).join("")}<p>${esc((gh.warnings||[]).join("; "))}</p>`;
    if(gh.status!=="disabled" && gh.runs?.length) {
      const failures=gh.runs.filter(run=>run.conclusion==="failure");
      $("github-detail").insertAdjacentHTML("beforeend",`<p>${failures.length} failed runs in the fetched sample; cancellations are separate.</p>${failures.slice(0,6).map(run=>`<div class="note-line">${esc(run.displayTitle)} · ${esc(run.conclusion)} · ${esc(run.headSha?.slice(0,7))}</div>`).join("")}`);
    }
    drawUsage(data.usage||{status:"unavailable",rows:[]});
    const tokenKeys=[{key:"audit",name:"audit",color:palette[0]},{key:"relabel",name:"relabel",color:palette[3]},{key:"other",name:"other",color:palette[4]}];
    const spend=runs=>Object.fromEntries(tokenKeys.map(k=>[k.key,runs.filter(t=>t.kind===k.key).reduce((n,t)=>n+t.tokens,0)]));
    const runs=rows.slice(0,selected+1).flatMap(row=>(row.tokens||[]).map(t=>({row,...t})));
    if(rows.some(row=>row.tokens?.length)) {
      bars("tokens-chart",timeline.map((r,index)=>({name:`${label(r)} · ${r.title}`,short:label(r),index,...spend(r.tokens||[])})),tokenKeys,"recorded tokens");
      let total=0,calls=0;const running=timeline.map(r=>{total+=(r.tokens||[]).reduce((n,t)=>n+t.tokens,0);calls+=(r.tokens||[]).reduce((n,t)=>n+t.calls,0);return {...r,spentTokens:total,spentCalls:calls};});
      lines("tokens-cumulative",running,[{name:"Tokens",color:palette[0],get:r=>r.spentTokens}],"tokens");
    } else ["tokens-chart","tokens-cumulative"].forEach(id=>empty(id,"No commit message on this ref records token usage."));
    const owners=[...new Set(runs.map(t=>t.change||"unattributed"))];
    bars("tokens-change",owners.map(name=>({name,...spend(runs.filter(t=>(t.change||"unattributed")===name))})),tokenKeys,"recorded tokens",true);
    table("tokens-table",["Merge","Change / step","Kind","Tokens","Tool calls","Commit"],runs.slice().reverse().map(t=>[esc(label(t.row)),`${esc(t.change||"—")} <span class="mono">${esc(t.step||"")}</span>`,esc(t.kind),fmt(t.tokens,0),fmt(t.calls,0),`<code title="${esc(t.subject)}">${esc(t.sha.slice(0,7))}</code>`]));
    if(runs.length)$("tokens-table").insertAdjacentHTML("afterbegin",`<p>${runs.length} runs · ${fmt(runs.reduce((n,t)=>n+t.tokens,0),0)} tokens · ${fmt(runs.reduce((n,t)=>n+t.calls,0),0)} tool calls up to ${esc(label(r))}.</p>`);
    $("method").innerHTML=`<p>Source: local <code>${esc(data.ref)}</code> at <code>${esc(data.head)}</code>. Generated ${esc(data.generated)}. Refresh reloads local refs; it never fetches, changes Git state or runs gates.</p><p>Snapshot metrics include committed files only. Drift sees backticked identifiers and source occurrences, not prose meaning; comments and strings are only partially excluded. No later vocabulary is added to earlier snapshots. The permutation band is a comparison distribution, not a confidence interval. A missing or malformed source is never a pass. Evidence and closure rules remain Redline’s own.</p><p>Builds 1–4 and Jev have no tracked O-item counts here. Planned builds cannot be declared complete from a zero count. Token counts come from local Claude Code and Codex session logs (totals only) and from commit messages that record runs; deployment and service-migration data are not inferred.</p><p>Selected-snapshot diagnostics (${r.warnings.length}): ${esc(r.warnings.join("; ")||"none")}</p>`;
  }
  function choose(index){selected=Math.max(0,Math.min(data.rows.length-1,index));render();}
  function stop(){if(timer)clearInterval(timer);timer=null;$("play").textContent="▶ Replay";}
  async function load() {
    stop();$("refresh").disabled=true;$("error").hidden=true;
    try {
      const response=await fetch("/api/data",{cache:"no-store"});
      if(!response.ok)throw new Error(`Data request failed (${response.status}). ${await response.text()}`);
      data=await response.json();if(!data.rows?.length)throw new Error("No snapshots in the selected ref.");
      selected=data.rows.length-1;$("history").max=selected;$("history").disabled=false;
      $("source").replaceChildren();
      [`${data.repo} / ${data.ref}`,`${data.head.slice(0,12)} · ${data.rows.length} snapshots`,data.behind?`${data.behind} commits behind origin/main · try --ref origin/main`:"Local refs · read-only"].forEach(text=>{const d=document.createElement("div");d.textContent=text;$("source").appendChild(d);});
      $("loading").hidden=true;$("dashboard").hidden=false;render();
      if(data.github.status!=="disabled")ask(data);
    }catch(error){$("error").textContent=error.message;$("error").hidden=false;$("loading").hidden=true;}
    finally{$("refresh").disabled=false;}
  }
  // Local data renders first, with GitHub's last saved answer; the fresh answer follows.
  async function ask(shown) {
    try {
      const response=await fetch("/api/github",{cache:"no-store"});
      if(!response.ok)throw new Error(`GitHub request failed (${response.status})`);
      const fresh=await response.json();if(data!==shown)return;
      data.github=fresh.github;const last=data.rows.at(-1);if(last.sha===fresh.sha)last.note=fresh.note;render();
    }catch(error){if(data===shown){data.github={...data.github,warnings:[...(data.github.warnings||[]),error.message]};render();}}
  }
  $("history").addEventListener("input",ev=>{stop();choose(Number(ev.target.value));});
  $("latest").addEventListener("click",()=>{stop();choose(data.rows.length-1);});
  $("play").addEventListener("click",()=>{if(timer)return stop();if(selected===data.rows.length-1)choose(0);$("play").textContent="Ⅱ Pause";timer=setInterval(()=>{if(selected>=data.rows.length-1)return stop();choose(selected+1);},900);});
  $("refresh").addEventListener("click",load);
  new ResizeObserver(()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{if(data)render();},150);}).observe(document.querySelector("main"));
  load();
})();
