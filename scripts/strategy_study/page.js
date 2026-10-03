'use strict';
const P=JSON.parse(document.getElementById('studyPayload').textContent),DATA=P.data,ROWS=DATA.rows,N=P.narrative;
const GUIDE=P.guide||{},familyOrder=['T','D','G','C','P','W'];
const familyNames={T:'曝光时长与门槛保护',D:'科学收益估计',G:'高度软偏好',C:'覆盖欠账优先',P:'选场搜索宽度',W:'粗预报方向避险'};
const guideFamily=f=>(GUIDE.families||[]).find(v=>v.id===f)||{};
const familyTitle=f=>guideFamily(f).title||familyNames[f]||f;
const textParagraph=s=>s?`<p>${esc(s)}</p>`:'';
const $=id=>document.getElementById(id),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=(v,d=2)=>typeof v==='number'&&Number.isFinite(v)?v.toLocaleString('zh-CN',{minimumFractionDigits:d,maximumFractionDigits:d}):'—';
const signed=(v,d=2)=>typeof v==='number'?`${v>0?'+':''}${fmt(v,d)}`:'—';
const color=v=>v<0?'#b64837':'#087e82',tone=v=>v<0?'negative':v>0?'positive':'';
const cards=['demo','dev-season','holdout-season','holdout-stress'],devCards=cards.slice(0,2),holdCards=cards.slice(2),combos=['DP','DG','DT','DPG','DTGP','DTGPCW'],families=['baseline','T','D','G','P','C','W',...combos];
const isHold=c=>c.startsWith('holdout-'),cardName=c=>({'demo':'demo','dev-season':'dev-season','holdout-season':'holdout-season','holdout-stress':'holdout-stress'}[c]||c);
const role=c=>isHold(c)?'保留 · 研究生成卡':c==='demo'?'开发 · 官方教学卡':'开发 · 研究生成卡';
const byId=new Map(ROWS.map(r=>[r.run_id,r]));
const baselineIds={'demo':'r1-official-demo','dev-season':'r1-official-dev-season','holdout-season':'r5-baseline-holdout-season','holdout-stress':'r5-baseline-holdout-stress'};
const baseline=c=>byId.get(baselineIds[c]);
// 参数身份来自已冻结选择，绝不从保留分数挑 run。T 不是 R2 的严格格内配置。
const frozen={T:'r3-t-cap900-conditional',D:'r2-d-linear',G:'r2-g-soft05',P:'r3-p-p12',C:'r2-c-soft06',W:'r2-w-forecast02',DP:'r4-dp-frozen01',DG:'r4-dg-frozen01',DT:'r4-dt-frozen01',DPG:'r4-dpg-frozen02',DTGP:'r4-dtgp-frozen02',DTGPCW:'r4-dtgpcw-frozen02'};
const frozenRow=(f,c)=>f==='baseline'?baseline(c):byId.get(`${isHold(c)?'r5-'+f.toLowerCase():frozen[f]}-${c}`);
const delta=r=>r&&baseline(r.card)?r.total-baseline(r.card).total:null;
const scienceDelta=r=>r.components.sum_best_scores-baseline(r.card).components.sum_best_scores;
const mean=vs=>vs.length&&vs.every(v=>typeof v==='number')?vs.reduce((s,v)=>s+v,0)/vs.length:null;
const averages=f=>({dev:mean(devCards.map(c=>delta(frozenRow(f,c)))),hold:mean(holdCards.map(c=>delta(frozenRow(f,c))))});
const family=r=>r.family||(/baseline|official|harness-demo/.test(r.run_id)?'baseline':r.run_id.includes('idle')?'idle':'—');
const familyText={baseline:'官方 baseline',T:'T · 条件长曝',D:'D · 指数1',G:'G · 高度0.5',P:'P · 12锚点',C:'C · 覆盖0.6',W:'W · 粗预报0.2'};
const profile=f=>familyText[f]||f;
const variantNames={'slot900':'严格天气格内','cap900':'只限900秒，允许跨格','cap900-conditional':'900秒＋必要长曝','linear':'科学指数1','power15':'科学指数1.5','power075':'科学指数0.75','soft05':'高度软权0.5','p6':'6锚点','p12':'12锚点','frozen01':'冻结组合','frozen02':'冻结组合','neutral':'全关控制'};
const configName=r=>family(r)==='baseline'?'官方 baseline':`${family(r)} · ${variantNames[r.variant]||r.variant||(family(r)==='C'?'覆盖0.6':family(r)==='W'?'粗预报0.2':'初始配置')}`;
const componentNames={sum_best_scores:'科学分',required_penalty:'required 罚分',uniformity_penalty:'覆盖罚分',observation_request_reward:'请求奖励',report_settlement:'report 净奖罚'};
const componentKeys=Object.keys(componentNames);
const categoryNames={'R1':'R1 基础验收','control':'control 全关','integration-verification':'integration 等价','intentional-timeout':'故意 timeout guard','strategy':'策略 / baseline','unknown':'未分类'};
const stateNames={'completed-full-season':'整段完成','completed-early':'提前结束（idle）','expected-timeout':'预期超时验证','completed-partial':'部分完成','failed':'执行失败','running':'运行中','missing-outputs':'缺少输出','unknown':'未知'};
const stageDescriptions={R1:'复现基线与执行器可靠性',R2:'六家族独立单因素试验',R3:'T / D / P 有限反馈迭代',R4:'已测参数组合与14项迁移验收',R5:'13个冻结配置 × 两保留卡，只评估'};
const svgText=(x,y,t,attrs='')=>`<text x="${x}" y="${y}" ${attrs}>${esc(t)}</text>`;
function table(headers,body,classes='compact'){return `<table class="${classes}"><thead><tr>${headers.map(h=>`<th>${h}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table>`;}
function width(id){return Math.max(280,$(id).parentElement.clientWidth-2);}
function bars(id,items){
 const w=width(id),left=w<400?108:130,right=64,plot=w-left-right,step=38,h=items.length*step+42,vals=items.map(i=>i.value),min=Math.min(0,...vals),max=Math.max(0,...vals),span=max-min||1;
 const X=v=>left+(v-min)/span*plot,z=X(0);let s=`<line class="zero" x1="${z}" y1="4" x2="${z}" y2="${h-30}"/>`;
 items.forEach((item,i)=>{const y=i*step+14,x=X(item.value);s+=svgText(left-10,y+13,item.label,'text-anchor="end"');s+=`<rect x="${Math.min(z,x)}" y="${y}" width="${Math.max(.7,Math.abs(x-z))}" height="22" fill="${item.color||color(item.value)}" opacity="${item.label==='总分'?1:.75}"/>`;s+=svgText(w-2,y+16,item.display??signed(item.value),'text-anchor="end"');});
 [min,max].filter((v,i,a)=>i===a.indexOf(v)).forEach(v=>{s+=svgText(X(v),h-7,fmt(v,0),'text-anchor="middle"');});
 $(id).setAttribute('viewBox',`0 0 ${w} ${h}`);$(id).innerHTML=s;
}
function evidenceHref(raw){return '../experiments/v4/results/'+raw;}
function sourceHref(raw){if(!raw)return null;const marker='/sky_survey_agent_competition/';return raw.includes(marker)?'../'+raw.split(marker)[1]:null;}
function runLinks(r){
 const base=`../experiments/v4/runs/${encodeURIComponent(r.run_directory_name)}/`,links=[['manifest',base+'manifest.json'],['归档配置',base+'config.json'],['源码快照',base+'source_snapshot/'],['metrics',base+'metrics.json']];
 if(r.evidence_links['output/score_report.json'])links.push(['官方 score report',evidenceHref(r.evidence_links['output/score_report.json'])]);
 const source=sourceHref(r.agent_source),config=sourceHref(r.config_source);if(source)links.push(['策略源码',source+'/planner.py']);if(config)links.push(['参数源文件',config]);
 return links.map(([label,url])=>`<a href="${esc(url)}">${esc(label)}</a>`).join('');
}
function fullEvidence(r){return `<details><summary>证据与配置</summary><div class="evidence">${runLinks(r)}${Object.entries(r.evidence_links).filter(([k])=>k.startsWith('output/')&&k!=='output/score_report.json').map(([k,v])=>`<a href="${esc(evidenceHref(v))}">${esc(k)}</a>`).join('')}</div><pre>${esc(JSON.stringify(r.config,null,2))}</pre></details>`;}
function attachNarrative(id,key){$(id).innerHTML=N[key]||'';}
function overview(){
 for(const id of ['lead','online','generated','limits','stress','interaction','selection','gap','invalid'])attachNarrative(id,id);
 $('judgments').innerHTML=[1,2,3,4].map(i=>N['judgment'+i]).join('');$('nextSteps').innerHTML=[1,2,3,4].map(i=>N['next'+i]).join('');
 $('stageOverview').innerHTML=Object.entries(stageDescriptions).map(([s,t])=>`<div class="stage-line"><b>${s}</b>${t}</div>`).join('');
 $('cardOverview').innerHTML=cards.map(c=>{const r=baseline(c);return `<tr><td>${c}</td><td><span class="badge ${isHold(c)?'holdout':''}">${role(c)}</span></td><td>${r.card_nights} / ${r.card_targets}</td></tr>`;}).join('');
 const counts=DATA.inventory_counts.by_evaluation_state;$('snapshotInfo').textContent=`研究日期：北京时间 2026-10-02。数据快照：${new Date(DATA.generated_at_utc).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}（北京时间）。共 ${ROWS.length} 条：${counts['completed-full-season']} 条整段、${counts['completed-early']} 条 idle 提前结束、${counts['expected-timeout']} 条故意超时验证。14项组合等价验收包括12个 integration 与2个全关 control。`;
}
function renderGuide(){
 if(GUIDE.title)$('pageTitle').textContent=GUIDE.title;
 $('guideIntro').innerHTML=(GUIDE.intro||[]).map(textParagraph).join('')||'<p class="note">导读说明待更新。以下分数总览已可直接查看。</p>';
 $('readingOrder').innerHTML=(GUIDE.reading_order||[]).map(v=>`<a href="${esc(v.href)}"><strong>${esc(v.label)}</strong><span>${esc(v.description)}</span></a>`).join('');
 $('baselineGuide').innerHTML=GUIDE.baseline?`<h2>${esc(GUIDE.baseline.title)}</h2>${textParagraph(GUIDE.baseline.description)}`:'';
 const fields=[['question','想回答什么'],['change','具体改了什么'],['motivation','传统观测动机'],['tradeoff','为什么这样试／代价'],['observed','观察到的结果'],['iteration','为何迭代或停止'],['value','研究价值']];
 $('strategyCards').innerHTML=familyOrder.map(f=>{const g=guideFamily(f),initial=iterations[f][0][0];return `<article class="strategy-explanation" id="family-${f}"><h3>${esc(familyTitle(f))}<span class="family-code">${f}</span></h3>${fields.map(([key,label])=>g[key]?`<div class="explanation-field"><h4>${label}</h4>${textParagraph(g[key])}</div>`:'').join('')}${!g.change?'<p class="note">该策略说明尚待更新。</p>':''}<div class="strategy-score-strip"><div><b>R2 初始配置 · 开发增量</b>${devCards.map(c=>{const r=byId.get(initial+'-'+c);return `<span>${c} <strong class="${tone(delta(r))}">${signed(delta(r))}</strong></span>`;}).join('')}</div><div><b>冻结配置 · 保留增量</b>${holdCards.map(c=>{const r=frozenRow(f,c);return `<span>${c.replace('holdout-','')} <strong class="${tone(delta(r))}">${signed(delta(r))}</strong></span>`;}).join('')}</div></div><p class="note">${esc(g.frozen_label||profile(f))}。初始开发列与冻结保留列可能采用不同参数；同参数迁移见<a href="#score-overview">冻结总览 B</a>。</p></article>`;}).join('');
 const g=GUIDE.combinations||{};$('combinationGuide').innerHTML=g.question?`<h3>组合试验想回答什么？</h3>${textParagraph(g.question)}<div class="combination-design">${(g.design||[]).map(v=>`<div><h4>${esc(v.id)} · ${esc(v.meaning)}</h4>${textParagraph(v.why)}</div>`).join('')}</div><h4>组合结果与研究价值</h4>${textParagraph(g.observed)}${textParagraph(g.value)}`:'';
 if(GUIDE.takeaways)$('judgments').innerHTML=GUIDE.takeaways.map(v=>`<h3>${esc(v.title)}</h3>${textParagraph(v.text)}`).join('');
}
function displayProfile(f){if(f==='baseline')return '官方 baseline';return guideFamily(f).frozen_label||GUIDE.combinations?.design?.find(v=>v.id===f)?.meaning||profile(f);}
function scoreCell(r,mode='total'){
 if(!r||!r.score_available)return '<td class="numeric"><span class="subtle">未运行／未取得</span></td>';
 const d=delta(r),value=mode==='delta'?signed(d):fmt(r.total),small=mode==='delta'?`总分 ${fmt(r.total)}`:`Δ ${signed(d)} · required 遗漏 ${r.required_missing}`;
 return `<td class="numeric"><button class="score-drill ${mode==='delta'?tone(d):''}" data-score-run="${esc(r.run_id)}" aria-label="${esc(configName(r)+' '+r.card+'，总分 '+fmt(r.total)+'，查看分项')}">${value}</button><span class="subtle">${small}</span></td>`;
}
function connectScoreDrill(){document.querySelectorAll('[data-score-run]').forEach(el=>el.addEventListener('click',()=>{selectRun(el.dataset.scoreRun);$('compare').scrollIntoView({block:'start',behavior:'auto'});}));}
function renderScoreOverviews(){
 const groups=[{id:'baseline',title:'参照：官方 baseline',defs:[['baseline','官方完整 Agent']]}];
 for(const f of familyOrder)groups.push({id:f,title:familyTitle(f)+'（'+f+'）',defs:iterations[f]});
 groups.push({id:'combined',title:'已测试参数的组合',defs:combos.map(f=>[frozen[f],f+' · '+displayProfile(f)])});
 let count=0;const body=groups.map(g=>`<tr class="score-group"><th colspan="5">${esc(g.title)}</th></tr>`+g.defs.map(([id,label])=>{count++;const rs=devCards.map(c=>id==='baseline'?baseline(c):byId.get(id+'-'+c)),avg=mean(rs.map(delta)),stage=rs.find(Boolean)?.stage_group||'—';return `<tr><th>${esc(label)}<span class="subtle">${id==='baseline'?'':esc(id)}</span></th><td>${stage}</td>${rs.map(r=>scoreCell(r)).join('')}<td class="numeric ${tone(avg)}">${signed(avg)}</td></tr>`;}).join('')).join('');
 $('developmentOverview').innerHTML=table(['家族 / 具体参数','阶段','demo 总分','dev-season 总分','开发平均 Δ'],body,'score-overview-table');$('developmentOverview').dataset.configurationCount=count;
 const mode=$('overviewDelta').checked?'delta':'total';$('frozenOverview').innerHTML=table(['冻结方案',...cards.map(c=>`${c}<span class="subtle">${isHold(c)?'保留：研究生成卡':c==='demo'?'开发：教学卡':'开发：研究生成卡'}</span>`)],families.map(f=>`<tr><th>${esc(displayProfile(f))}<span class="subtle">${f}${f==='DTGP'?' · 开封前选择':''}</span></th>${cards.map(c=>scoreCell(frozenRow(f,c),mode)).join('')}</tr>`).join(''),'score-overview-table frozen-table');$('frozenOverview').dataset.configurationCount=families.length;connectScoreDrill();
}
const officialCards=[{id:'alpha',label:'α'},{id:'beta',label:'β'},{id:'gamma',label:'γ'},{id:'delta',label:'δ'}];
function officialId(value){if(value&&typeof value==='object')value=value.card_id||value.id||value.name||value.label;const s=String(value||'').toLowerCase();for(const c of officialCards)if(s.includes(c.id)||s.includes(c.label))return c.id;return null;}
function strategyId(r){const raw=String(r.strategy_id||r.strategy||r.profile||r.family||r.config?.family||r.run_id||'').toLowerCase();if(raw.includes('dtgp'))return 'DTGP';if(raw.includes('baseline')||raw.includes('official'))return 'baseline';if(raw==='d'||raw.includes('dlinear')||raw.includes('d-linear')||/(?:^|-)d(?:-|$)/.test(raw))return 'D';return null;}
function externalRows(raw){
 if(!raw)return [];if(Array.isArray(raw))return raw;
 for(const k of ['rows','runs','results'])if(Array.isArray(raw[k]))return raw[k];
 if(raw.cards){const cs=Array.isArray(raw.cards)?raw.cards:Object.entries(raw.cards).map(([id,v])=>({...v,card_id:v.card_id||id}));return cs.flatMap(c=>{const rs=externalRows(c);return rs.map(r=>({...r,card_id:r.card_id||c.card_id||c.id||c.card}));});}
 return [];
}
function localRecord(f,c){return externalRows(P.external_results).find(r=>officialId(r.card_id||r.card||r.card_source||r.scenario_id||r.run_id)===c&&strategyId(r)===f);}
function officialTotal(r){if(!r||r.score_available===false)return null;for(const value of [r.total,r.score?.total,r.metrics?.total,r.result?.total,r.final_score])if(typeof value==='number'&&Number.isFinite(value))return value;return null;}
function screenshotRecord(c){const raw=P.leaderboard_screenshots;if(!raw)return null;const source=raw.cards||raw.scenarios||raw.rows||[];const cs=Array.isArray(source)?source:Object.entries(source).map(([id,v])=>({...v,card_id:v.card_id||id}));return cs.find(r=>officialId(r.card_id||r.card||r.id||r.label)===c);}
function screenshotDisplay(c,key){
 const r=screenshotRecord(c);if(!r)return null;const v=r.summary?.[key+'_total']??r[key]??r[key+'_score']??r.statistics?.[key];
 // summary 已由 Decimal 四舍五入；保留字面值，Number 只用于条形位置。
 if(typeof v==='string'&&/^-?\d+\.\d{2}$/.test(v))return v;
 return typeof v==='number'&&Number.isFinite(v)?fmt(v):null;
}
function screenshotValue(c,key){const display=screenshotDisplay(c,key);return display===null?null:Number(display.replace(/,/g,''));}
function cardAcquisition(c){const raw=P.external_results;if(!raw)return null;for(const source of [raw.cards,raw.downloads,raw.card_status]){if(!source)continue;const cs=Array.isArray(source)?source:Object.entries(source).map(([id,v])=>({...v,card_id:v.card_id||id}));const r=cs.find(r=>officialId(r.card_id||r.card||r.id||r.label)===c);if(r)return r;}return null;}
function unavailableLabel(r,c){if(GUIDE.external?.status==='official_cards_online_only')return '未提交（仅平台评测）';const state=String(r?.status||r?.run_status||cardAcquisition(c)?.status||P.external_results?.status||GUIDE.external?.status||'pending').toLowerCase();if(/blocked|incomplete|missing.*environment/.test(state))return '未运行（缺完整环境）';if(/download.*fail|unavailable/.test(state))return '下载／获取失败';if(/fail|error/.test(state))return '未完成／失败';if(/running/.test(state))return '运行中';return '待完成／未取得';}
function relativeExternalLink(raw){if(!raw)return null;const source=sourceHref(raw);if(source)return source;if(raw.startsWith('experiments/')||raw.startsWith('docs/'))return '../'+raw;if(raw.startsWith('http://')||raw.startsWith('https://'))return raw;return '../experiments/v4/external_evaluation/'+raw;}
function renderExternal(){
 const g=GUIDE.external||{};if(g.title)$('externalTitle').textContent=g.title;
 $('externalGuide').innerHTML=(g.selection||[]).map(v=>`<p><strong>${esc(v.id)}</strong> · ${esc(v.reason)}</p>`).join('')+textParagraph(g.limit);
 $('externalAnalysis').innerHTML=(g.analysis||[]).map(textParagraph).join('');
 const completed=officialCards.reduce((n,c)=>n+['baseline','D','DTGP'].filter(f=>officialTotal(localRecord(f,c.id))!==null).length,0);
 $('externalStatus').textContent=`${g.status==='official_cards_online_only'?'预定正式卡平台评测：'+completed+' / 12 已取得成绩。':'实际公开卡本地结果：'+completed+' / 12 已取得分数。'}${P.input_states.external.status==='loaded'?'此处展示事先固定的三组对照。':'评估记录尚未写入或暂不可读，缺失不填零。'}${g.status==='pending'?' 结果说明将在评估完成后更新。':''}${/blocked/.test(g.status||'')?' 完整环境不足，固定对照未运行。':''}`;
 const matrix=[['baseline','官方 baseline'],['D','科学收益估计 D（指数1）'],['DTGP','冻结组合 DTGP'],['median','截图中位数'],['top','截图最高分']];
 $('officialMatrix').innerHTML=table(['口径 / 方案',...officialCards.map(c=>c.label+' · '+c.id)],matrix.map(([id,label])=>`<tr><th>${label}<span class="subtle">${id==='median'||id==='top'?'用户截图，非本地模拟':g.status==='official_cards_online_only'?'预定正式卡对照，尚无平台成绩':'相同实际卡，本地官方评分器'}</span></th>${officialCards.map(c=>{const isScreenshot=id==='median'||id==='top',r=localRecord(id,c.id),value=isScreenshot?screenshotValue(c.id,id):officialTotal(r),localBase=officialTotal(localRecord('baseline',c.id));if(value===null)return `<td class="numeric"><span class="subtle">${isScreenshot?'截图值未知':unavailableLabel(r,c.id)}</span></td>`;const evidence=relativeExternalLink(r?.metrics_path||r?.manifest_path||r?.evidence_links?.metrics||r?.evidence_links?.['metrics.json']);return `<td class="numeric">${isScreenshot?screenshotDisplay(c.id,id):fmt(value)}<span class="subtle">${isScreenshot?'截图快照':id!=='baseline'&&localBase!==null?'Δ '+signed(value-localBase):'本地参照'}</span>${evidence?`<a class="subtle" href="${esc(evidence)}">原记录</a>`:''}</td>`;}).join('')}</tr>`).join(''),'score-overview-table official-table');
 $('officialCharts').innerHTML=officialCards.map(c=>{const items=matrix.map(([id,label])=>({label:id==='baseline'?'本地 baseline':id==='D'?'本地 D 指数1':id==='DTGP'?'本地 DTGP':label,value:id==='median'||id==='top'?screenshotValue(c.id,id):officialTotal(localRecord(id,c.id)),color:id==='median'||id==='top'?'#b77816':'#087e82'})).filter(v=>v.value!==null),known=items.length,missing=['baseline','D','DTGP'].filter(f=>officialTotal(localRecord(f,c.id))===null),statuses=missing.map(f=>unavailableLabel(localRecord(f,c.id),c.id)),localNote=missing.length===3&&new Set(statuses).size===1?`${g.status==='official_cards_online_only'?'预定':'本地'} baseline、D、DTGP：${statuses[0]}。`:missing.map((f,i)=>`本地 ${f}：${statuses[i]}。`).join(' ');return `<article class="official-chart"><h3>${c.label} · 实际公开练习卡</h3>${localNote?`<p class="note">${esc(localNote)}</p>`:''}<svg id="officialChart-${c.id}" role="img" aria-label="${c.label} 卡本地模拟与截图分数参照"></svg><p class="note">${known?`已取得 ${known} 项数值；条形为总分，不是排名。`:'尚无可绘制的数值。'} 缺失项不绘成零。</p></article>`;}).join('');
 officialCards.forEach(c=>{const items=matrix.map(([id,label])=>({label:id==='baseline'?'本地 baseline':id==='D'?'本地 D 指数1':id==='DTGP'?'本地 DTGP':label,value:id==='median'||id==='top'?screenshotValue(c.id,id):officialTotal(localRecord(id,c.id)),display:id==='median'||id==='top'?screenshotDisplay(c.id,id):fmt(officialTotal(localRecord(id,c.id))),color:id==='median'||id==='top'?'#b77816':'#087e82'})).filter(v=>v.value!==null);if(items.length)bars('officialChart-'+c.id,items);else{$('officialChart-'+c.id).setAttribute('viewBox','0 0 320 80');$('officialChart-'+c.id).innerHTML=svgText(10,40,'等待实际卡结果或截图记录');}});
 $('leaderboardScope').innerHTML=(P.leaderboard_screenshots?.limitations||[]).map(textParagraph).join('')+officialCards.map(c=>{const r=screenshotRecord(c.id),n=r?.sample_count??r?.summary?.n,evidence=relativeExternalLink(r?.screenshot_path);return `<p><strong>${c.label} 截图口径：</strong>${r?esc(r.scope||r.description||P.leaderboard_screenshots?.scope||'截图全部显示队伍的总分，包含负分。'):'未取得截图统计；中位数和最高分未知。'}${n!=null?' 样本数 '+esc(n)+'。':''}${evidence?` <a href="${esc(evidence)}">原截图</a>`:''}</p>`;}).join('');
 $('externalSources').innerHTML=[['external','正式卡结果 JSON'],['screenshots','用户截图记录 JSON']].filter(([key])=>P.input_states[key].status==='loaded').map(([key,label])=>`<a href="../${esc(P.input_states[key].path)}">${label}</a>`).join('')+(P.external_source_links||[]).map(v=>`<a href="../${esc(v.path)}">${esc(v.label)}</a>`).join('');
}
function validPlans(c,stage){return ROWS.filter(r=>r.card===c&&r.full_season_complete&&r.score_available&&(r.experiment_category==='strategy'||r.run_id===baselineIds[c])&&(stage==='all'||r.stage_group===stage));}
function refillPlans(preferred){
 const c=$('compareCard').value,s=$('compareStage').value,plans=validPlans(c,s),prior=preferred||$('compareRun').value;
 $('compareRun').innerHTML=plans.map(r=>`<option value="${esc(r.run_id)}">${r.stage_group} · ${esc(configName(r))}</option>`).join('');
 if(plans.some(r=>r.run_id===prior))$('compareRun').value=prior;else if(plans.some(r=>r.run_id===`${frozen.T}-${c}`))$('compareRun').value=`${frozen.T}-${c}`;
 renderCompare();
}
function renderCompare(){
 const r=byId.get($('compareRun').value),c=$('compareCard').value,b=baseline(c);$('compareScope').className='scope'+(isHold(c)?' holdout':'');
 $('compareScope').textContent=`当前：${c}｜${role(c)}｜阶段 ${$('compareStage').value==='all'?'全部策略阶段':$('compareStage').value}。${isHold(c)?'已开封评估；结果不用于策略改动。':'用于开发反馈；同卡基线固定。'}`;
 $('comparisonEmpty').hidden=!!r;$('comparisonContent').hidden=!r;if(!r){$('comparisonEmpty').textContent='该卡与阶段没有策略记录。请选择其他阶段；不会把无记录填为零。';return;}
 const d=delta(r);$('scoreFacts').innerHTML=[['baseline 总分',fmt(b.total)],['方案总分',fmt(r.total)],['同卡总增量',`<span class="${tone(d)}">${signed(d)}</span>`]].map(([k,v])=>`<div class="fact"><span>${k}</span><b class="num">${v}</b></div>`).join('');
 const parts=componentKeys.map(k=>({label:componentNames[k],value:r.components[k]-b.components[k]}));bars('componentChart',[{label:'总分',value:d},...parts]);
 $('componentTable').innerHTML=table(['分项','baseline','方案','增量'],componentKeys.map(k=>`<tr><td>${componentNames[k]}</td><td class="numeric">${fmt(b.components[k])}</td><td class="numeric">${fmt(r.components[k])}</td><td class="numeric ${tone(r.components[k]-b.components[k])}">${signed(r.components[k]-b.components[k])}</td></tr>`).join(''));
 $('taskFacts').innerHTML=table(['指标','baseline → 方案','变化'],[
 ['required 遗漏',`${b.required_missing} → ${r.required_missing}`,signed(r.required_missing-b.required_missing,0)],
 ['覆盖 J',`${fmt(b.coverage_jain,4)} → ${fmt(r.coverage_jain,4)}`,signed(r.coverage_jain-b.coverage_jain,4)],
 ['达标源数',`${fmt(b.coverage_qualified_targets,0)} → ${fmt(r.coverage_qualified_targets,0)}`,signed(r.coverage_qualified_targets-b.coverage_qualified_targets,0)],
 ['观测动作',`${b.observe_actions} → ${r.observe_actions}`,signed(r.observe_actions-b.observe_actions,0)],
 ['平均曝光 / 秒',`${fmt(b.actual_exposure_mean_seconds)} → ${fmt(r.actual_exposure_mean_seconds)}`,signed(r.actual_exposure_mean_seconds-b.actual_exposure_mean_seconds)],
 ['程序耗时 / 秒',`${fmt(b.runtime_seconds,3)} → ${fmt(r.runtime_seconds,3)}`,''],
 ['pace 变化',`${fmt(b.pace_change_count,0)} → ${fmt(r.pace_change_count,0)}`,'']].map(a=>`<tr>${a.map((v,i)=>`<td${i?' class="numeric"':''}>${v}</td>`).join('')}</tr>`).join(''));
 const f=family(r),gf=guideFamily(f);$('selectedMechanism').innerHTML=isHold(c)?`<p class="note">${profile(f)} 为开封前冻结候选。${f==='T'?'这里的 T 是条件长曝，与 R2 严格格内策略参数不同。':''}本次 ${stateNames[r.evaluation_state]}，负总分不等于执行失败。</p>`:f==='baseline'?textParagraph(GUIDE.baseline?.description)||'<p class="note">本图以官方完整 Agent 作为同卡参照。</p>':combos.includes(f)?'<p class="note">该组合使用已经测试过的参数。本次运行的分项见上表；组成项与描述性交互量见下方组合面板。组合没有重新调参。</p>':`<p class="note">${r.stage_group==='R3'?'该家族开发过程总结（两张开发卡）':'该初始配置的两张开发卡机制记录'}。本次运行的数值见上表。</p>`+(r.stage_group==='R3'?'<h4>结果解释</h4>'+(N[f+'_iteration']||'')+(gf.iteration?'<h4>为何迭代或停止</h4>'+textParagraph(gf.iteration):''):(gf.observed?textParagraph(gf.observed):N[f]||''));
 $('selectedLinks').innerHTML=runLinks(r);$('componentChart').setAttribute('aria-label',`${c} ${configName(r)} 对 baseline 的总分增量 ${signed(d)}；各分项见下表。`);
}
function selectRun(id){const r=byId.get(id);if(!r)return;$('compareCard').value=r.card;$('compareStage').value=r.stage_group;refillPlans(id);}
const iterations={T:[['r2-t-slot900','初始：严格格内'],['r3-t-cap900','反馈1：只限900秒'],['r3-t-cap900-conditional','反馈2：必要长曝']],D:[['r2-d-linear','初始：指数1'],['r3-d-power15','反馈1：指数1.5'],['r3-d-power075','反馈2：指数0.75']],P:[['r2-p-p6','初始：6锚点'],['r3-p-p12','反馈1：12锚点']],G:[['r2-g-soft05','初始：高度0.5']],C:[['r2-c-soft06','初始：覆盖0.6']],W:[['r2-w-forecast02','初始：粗预报0.2']]};
function renderIterations(){
 const f=$('iterFamily').value,steps=iterations[f],chosen=$('iterCard').value,cs=chosen==='both'?devCards:[chosen],metric=$('iterMetric').value,get=r=>metric==='science'?scienceDelta(r):metric==='missing'?r.required_missing-baseline(r.card).required_missing:delta(r),series=cs.map((c,i)=>({card:c,color:i?'#b77816':'#3465bd',values:steps.map(([id])=>get(byId.get(id+'-'+c)))}));
 $('iterationScope').textContent=`当前：${f} 家族｜${cs.join(' + ')}｜${$('iterMetric').selectedOptions[0].textContent}。${steps.length===1?'本轮只有初始配置，没有 R3 调参。':'连线表示试验次序，不表示连续参数插值。'}`;
 const w=width('iterationChart'),h=285,left=52,right=22,top=26,bottom=65,vs=series.flatMap(s=>s.values),lo=Math.min(0,...vs),hi=Math.max(0,...vs),span=hi-lo||1,min=lo-span*.12,max=hi+span*.12,X=i=>left+(steps.length===1?.5:i/(steps.length-1))*(w-left-right),Y=v=>h-bottom-(v-min)/(max-min)*(h-top-bottom);
 let s='';for(let i=0;i<5;i++){let v=min+(max-min)*i/4;s+=`<line class="axis" x1="${left}" x2="${w-right}" y1="${Y(v)}" y2="${Y(v)}"/>`+svgText(left-7,Y(v)+4,fmt(v,0),'text-anchor="end"');}s+=`<line class="zero" x1="${left}" x2="${w-right}" y1="${Y(0)}" y2="${Y(0)}"/>`;
 series.forEach(ser=>{s+=`<polyline fill="none" stroke="${ser.color}" stroke-width="2.4" points="${ser.values.map((v,i)=>X(i)+','+Y(v)).join(' ')}"/>`;ser.values.forEach((v,i)=>{s+=`<circle class="point iter-point" tabindex="0" role="button" aria-label="${esc(steps[i][1]+' '+ser.card+' '+signed(v))}" data-run="${steps[i][0]}-${ser.card}" cx="${X(i)}" cy="${Y(v)}" r="5" fill="${ser.color}"><title>${esc(steps[i][1]+' · '+ser.card+'：'+signed(v))}</title></circle>`;});});
 steps.forEach(([id,label],i)=>{s+=svgText(X(i),h-42,label.split('：')[0],'text-anchor="middle"')+svgText(X(i),h-24,label.split('：')[1],'text-anchor="middle"');});$('iterationChart').setAttribute('viewBox',`0 0 ${w} ${h}`);$('iterationChart').innerHTML=s;
 $('iterationTable').innerHTML=`<p class="chart-legend">${series.map(s=>`<span><i style="background:${s.color}"></i>${s.card}</span>`).join('')}</p>`+table(['次序 / 配置','卡片','总分','总增量','科学增量','required 遗漏','均长 / 秒','对照'],steps.flatMap(([id,label])=>cs.map(c=>{const r=byId.get(id+'-'+c);return `<tr><td>${label}${frozen[f]===id?'<span class="subtle selection-note">开封前冻结候选</span>':''}</td><td>${c}</td><td class="numeric">${fmt(r.total)}</td><td class="numeric ${tone(delta(r))}">${signed(delta(r))}</td><td class="numeric">${signed(scienceDelta(r))}</td><td class="numeric">${r.required_missing}</td><td class="numeric">${fmt(r.actual_exposure_mean_seconds)}</td><td><button data-run="${r.run_id}" class="pick-run">看分项</button></td></tr>`;})).join(''));
 $('iterationNarrative').innerHTML=N[f]+(N[f+'_iteration']||'');
 document.querySelectorAll('.iter-point,.pick-run').forEach(el=>{el.addEventListener('click',()=>selectRun(el.dataset.run));if(el.classList.contains('iter-point'))el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();selectRun(el.dataset.run);}});});
}
let selectedCombo={family:'DTGP',card:'dev-season'};
function renderCombinations(){
 const max=Math.max(...combos.flatMap(f=>cards.map(c=>Math.abs(delta(frozenRow(f,c))))),1);
 $('comboMatrix').innerHTML=table(['组合',...cards.map(c=>`${c}<small>${isHold(c)?'保留 R5':'开发 R4'}</small>`)],combos.map(f=>`<tr><th>${f}${f==='DTGP'?'<small class="selection-note">开封前选择</small>':''}</th>${cards.map(c=>{const d=delta(frozenRow(f,c)),neg=d<0,px=Math.abs(d)/max*50;return `<td><button data-combo="${f}" data-card="${c}" aria-pressed="${f===selectedCombo.family&&c===selectedCombo.card}" aria-label="${f} ${c} 总分增量 ${signed(d)}；查看分项"><span class="${tone(d)}">${signed(d)}</span><div class="mini"><i style="left:${neg?50-px:50}%;width:${px}%;background:${color(d)}"></i></div></button></td>`;}).join('')}</tr>`).join(''),'matrix');
 document.querySelectorAll('[data-combo]').forEach(b=>b.addEventListener('click',()=>{selectedCombo={family:b.dataset.combo,card:b.dataset.card};renderInteraction();document.querySelectorAll('[data-combo]').forEach(v=>v.setAttribute('aria-pressed',String(v===b)));selectRun(frozenRow(selectedCombo.family,selectedCombo.card).run_id);}));renderInteraction();
}
function renderInteraction(){
 const {family:f,card:c}=selectedCombo,r=frozenRow(f,c),actual=delta(r),parts=[...f].map(sf=>({family:sf,row:frozenRow(sf,c)})),sum=parts.reduce((s,p)=>s+delta(p.row),0),interaction=actual-sum;
 $('interactionTitle').textContent=`${f} × ${c}`;$('interactionFacts').innerHTML=`<p class="scope ${isHold(c)?'holdout':''}">${role(c)}｜实际组合增量 ${signed(actual)}；单项和 ${signed(sum)}。</p><p>描述性交互量：<b class="${tone(interaction)}">${signed(interaction)}</b> 分</p>`;
 bars('interactionChart',[{label:'实际组合增量',value:actual},{label:'冻结单项之和',value:sum},{label:'交互量',value:interaction}]);
 $('interactionTable').innerHTML=table(['组成单项（同冻结参数）','同卡增量'],parts.map(p=>`<tr><td>${profile(p.family)}</td><td class="numeric">${signed(delta(p.row))}</td></tr>`).join(''));
 $('comboTransferNarrative').innerHTML=isHold(c)?N.T_transfer+N.CW_transfer:'<p class="note">单项参数：D指数1、T条件长曝、G高度0.5、P12锚点；C/W为R2初始强度。非加性可来自作用重叠和整季轨迹分叉，不能看成另一笔评分罚款。</p>';
}
function renderTransfer(){
 const filter=$('transferFilter').value,fs=families.filter(f=>filter==='all'||f==='baseline'||(filter==='single'?f.length===1:f.length>1)),pick=$('transferPick').value;
 if([...$('transferPick').options].map(o=>o.value).join('|')!==fs.join('|')){$('transferPick').innerHTML=fs.map(f=>`<option value="${f}">${profile(f)}</option>`).join('');$('transferPick').value=fs.includes(pick)?pick:fs.includes('DTGP')?'DTGP':'D';}
 const selected=$('transferPick').value,pts=fs.map(f=>({f,...averages(f)})),w=width('transferChart'),h=w<400?355:410,left=58,right=25,top=32,bottom=65,vals=pts.flatMap(p=>[p.dev,p.hold]),lo=Math.min(0,...vals),hi=Math.max(0,...vals),pad=(hi-lo||1)*.17,min=lo-pad,max=hi+pad,X=v=>left+(v-min)/(max-min)*(w-left-right),Y=v=>h-bottom-(v-min)/(max-min)*(h-top-bottom);
 let s='';for(let i=0;i<5;i++){const v=min+(max-min)*i/4;s+=`<line class="axis" x1="${left}" x2="${w-right}" y1="${Y(v)}" y2="${Y(v)}"/><line class="axis" x1="${X(v)}" x2="${X(v)}" y1="${top}" y2="${h-bottom}"/>`+svgText(left-8,Y(v)+4,fmt(v,0),'text-anchor="end"')+svgText(X(v),h-bottom+21,fmt(v,0),'text-anchor="middle"');}
 s+=`<line x1="${X(min)}" x2="${X(max)}" y1="${Y(min)}" y2="${Y(max)}" stroke="#8a9ba8" stroke-dasharray="5 5"/><line class="zero" x1="${X(0)}" x2="${X(0)}" y1="${top}" y2="${h-bottom}"/><line class="zero" x1="${left}" x2="${w-right}" y1="${Y(0)}" y2="${Y(0)}"/>`;
 pts.forEach(p=>{const col=p.f==='DTGP'?'#b77816':p.f==='DPG'?'#706088':'#087e82',label=p.f==='DTGP'||p.f==='DPG'||p.f==='D'||p.f===selected,anchor=X(p.dev)>w-100?'end':'start',tx=X(p.dev)+(anchor==='end'?-11:11),ty=Y(p.hold)+(p.f==='D'?18:-10);s+=`<g class="point transfer-point" tabindex="0" role="button" data-profile="${p.f}" aria-label="${esc(profile(p.f))}，开发平均增量 ${signed(p.dev)}，保留平均增量 ${signed(p.hold)}"><title>${esc(profile(p.f)+'：开发 '+signed(p.dev)+'；保留 '+signed(p.hold))}</title><circle cx="${X(p.dev)}" cy="${Y(p.hold)}" r="${p.f===selected?8:6}" fill="${p.f.length>1?col:'white'}" stroke="${col}" stroke-width="${p.f===selected?3:2}"/>${label?svgText(tx,ty,p.f,'text-anchor="'+anchor+'"'):''}</g>`;});
 s+=svgText(left,17,'保留平均增量 / 分')+svgText(w-right,h-14,'开发平均增量 / 分','text-anchor="end"');$('transferChart').setAttribute('viewBox',`0 0 ${w} ${h}`);$('transferChart').innerHTML=s;
 document.querySelectorAll('.transfer-point').forEach(el=>{const choose=()=>{$('transferPick').value=el.dataset.profile;renderTransfer();};el.addEventListener('click',choose);el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose();}});});
 const a=averages(selected);$('transferFacts').innerHTML=`<h3>${profile(selected)}</h3>${selected==='DTGP'?'<p class="selection-note">开封前已登记的选择</p>':''}${selected==='DPG'?'<p>本轮两个保留样本中的最高平均增量；没有据此重新调参。</p>':''}<div class="facts"><div class="fact"><span>开发平均增量</span><b class="num ${tone(a.dev)}">${signed(a.dev)}</b></div><div class="fact"><span>保留平均增量</span><b class="num ${tone(a.hold)}">${signed(a.hold)}</b></div></div>`+table(['对应卡与 run','总分','同卡增量'],cards.map(c=>{const r=frozenRow(selected,c);return `<tr><td>${c}<span class="subtle">${r.run_id}</span></td><td class="numeric">${fmt(r.total)}</td><td class="numeric">${signed(delta(r))}</td></tr>`;}).join(''))+'<p class="note">开发记录使用同一冻结候选；T为必要长曝，P为12锚点。两张卡等权平均，非显著性检验。</p>';
 $('transferNarrative').innerHTML=N.transfer;$('transferTable').innerHTML=table(['冻结方案',...cards.map(c=>c+' Δ'),'开发平均 Δ','保留平均 Δ'],fs.map(f=>{const a=averages(f);return `<tr><td>${profile(f)}</td>${cards.map(c=>`<td class="numeric">${signed(delta(frozenRow(f,c)))}</td>`).join('')}<td class="numeric">${signed(a.dev)}</td><td class="numeric">${signed(a.hold)}</td></tr>`;}).join(''));
}
function renderRuns(){
 const stage=$('runStage').value,card=$('runCard').value,category=$('runCategory').value,status=$('runStatus').value,q=$('runSearch').value.trim().toLowerCase(),rs=ROWS.filter(r=>(stage==='all'||r.stage_group===stage)&&(card==='all'||r.card===card)&&(category==='all'||r.experiment_category===category)&&(status==='all'||r.evaluation_state===status)&&(!q||[r.run_id,r.family,r.variant,JSON.stringify(r.config)].join(' ').toLowerCase().includes(q)));
 $('runCount').textContent=`显示 ${rs.length} / ${ROWS.length} 条记录；其中整段 ${rs.filter(r=>r.full_season_complete).length}，预期超时 ${rs.filter(r=>r.intentional_timeout).length}。`;
 $('runsBody').innerHTML=rs.map(r=>`<tr><td><b class="run-id">${esc(r.run_id)}</b><span class="subtle">${esc(configName(r))}</span></td><td>${esc(r.stage)}<br><span class="badge ${r.intentional_timeout?'guard':r.experiment_category==='control'?'control':''}">${esc(categoryNames[r.experiment_category]||r.experiment_category)}</span></td><td>${r.card}<span class="subtle">${isHold(r.card)?'保留':'开发'}</span></td><td class="numeric">${fmt(r.total)}</td><td class="numeric">${fmt(r.components.sum_best_scores)}</td><td class="numeric">${fmt(r.required_missing,0)}</td><td class="numeric">${fmt(r.coverage_jain,4)}<span class="subtle">${fmt(r.coverage_qualified_targets,0)} 个达标</span></td><td class="numeric">${fmt(r.observe_actions,0)}<span class="subtle">${fmt(r.actual_exposure_mean_seconds)}</span></td><td class="numeric">${fmt(r.runtime_seconds,3)}<span class="subtle">pace ${fmt(r.pace_change_count,0)}</span></td><td><span class="state-note">${stateNames[r.evaluation_state]||r.evaluation_state}</span><span class="subtle">${esc(r.termination_reason||'')}</span>${fullEvidence(r)}</td></tr>`).join('')||'<tr><td colspan="10">没有匹配记录。空列表不表示零分。</td></tr>';
}
function init(){
 overview();renderGuide();renderScoreOverviews();renderExternal();$('compareCard').innerHTML=cards.map(c=>`<option value="${c}">${c} · ${isHold(c)?'保留':'开发'}</option>`).join('');$('compareCard').value='dev-season';
 for(const [id,values,names] of [['runStage',[...new Set(ROWS.map(r=>r.stage_group))].sort(),null],['runCard',cards,null],['runCategory',[...new Set(ROWS.map(r=>r.experiment_category))].sort(),categoryNames],['runStatus',[...new Set(ROWS.map(r=>r.evaluation_state))].sort(),stateNames]])$(id).innerHTML+=values.map(v=>`<option value="${esc(v)}">${esc(names?.[v]||v)}</option>`).join('');
 ['compareCard','compareStage'].forEach(id=>$(id).addEventListener('change',()=>refillPlans()));$('compareRun').addEventListener('change',renderCompare);
 ['iterFamily','iterCard','iterMetric'].forEach(id=>$(id).addEventListener('change',renderIterations));['transferFilter','transferPick'].forEach(id=>$(id).addEventListener('change',renderTransfer));['runStage','runCard','runCategory','runStatus'].forEach(id=>$(id).addEventListener('change',renderRuns));$('runSearch').addEventListener('input',renderRuns);
 $('resetTable').addEventListener('click',()=>{['runStage','runCard','runCategory','runStatus'].forEach(id=>$(id).value='all');$('runSearch').value='';renderRuns();});
 $('overviewDelta').addEventListener('change',renderScoreOverviews);
 $('downloadJson').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(DATA,null,2)+'\n'],{type:'application/json;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='all_runs.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
 refillPlans('r3-t-cap900-conditional-dev-season');renderIterations();renderCombinations();renderTransfer();renderRuns();
 let timer;new ResizeObserver(()=>{clearTimeout(timer);timer=setTimeout(()=>{renderCompare();renderIterations();renderInteraction();renderTransfer();renderExternal();},100);}).observe($('main'));
 // 只暴露计算接口供构建后核对，不执行模拟或读取外部文件。
 window.study={rowCount:ROWS.length,baseline,frozenRow,delta,averages,iterations,selectRun,externalRows,localRecord,officialTotal,screenshotValue,screenshotDisplay,renderExternal};
}
init();
