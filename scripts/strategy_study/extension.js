'use strict';
// 第二批与首轮分开建索引、参照和证据链接；不读取或运行模拟器。
const EXT=P.extension_data||{},EXTG=P.extension_guide||{},EXTROWS=EXT.rows||[],EXTREFS=EXT.reference_rows||[];
const extFamilies=['H','E','Q','M','F','J'],extDevCards=['demo','dev-season'];
const extHoldCards=['ext-holdout-a','ext-holdout-b','ext-holdout-c','ext-holdout-d'];
const extStageNames={N1:'N1 包装验收',N2:'N2 初版',N3:'N3 修订',N4:'N4 组合',N5:'N5 冻结评估','integration-verification':'全关等价验收'};
const extFamily=f=>(EXTG.families||[]).find(v=>v.id===f)||{};
const extScore=r=>r&&r.score_available!==false&&typeof r.total==='number'&&Number.isFinite(r.total)?r.total:null;
const extDelta=r=>r&&r.delta_vs_D_available===true&&typeof r.delta_vs_D==='number'?r.delta_vs_D:null;
const extCase=r=>r.case_id||[r.family,r.variant].filter(Boolean).join(':');
const extHold=c=>extHoldCards.includes(c);
function extReference(card){return EXTREFS.find(r=>r.card===card&&extCase(r)==='D-linear')||EXTROWS.find(r=>r.card===card&&extCase(r)==='D-linear'&&extScore(r)!==null);}
function extLabel(id,row){
 const declared=[...(EXTG.cases||[]),...(EXTG.frozen_cases||[])].find(v=>(v.case_id||v.id)===id);
 if(declared?.label)return declared.label;
 if(id==='D-linear')return 'D · 科学指数1';
 if(id==='official-baseline')return '官方 baseline';
 if(id==='DTGP-frozen02')return '旧 DTGP · 首轮冻结参数';
 const family=row?.family||id.split(':')[0],title=extFamily(family).title;
 return title?`${title} · ${row?.variant||id.split(':').slice(1).join(':')}`:id;
}
function extEvidenceHref(raw){if(!raw)return null;const source=sourceHref(raw);if(source)return source;if(raw.startsWith('experiments/')||raw.startsWith('docs/'))return '../'+raw;return '../experiments/v4/extension/results/'+raw;}
function extEvidence(r){
 const links=Object.entries(r.evidence_links||{}).filter(([key])=>['manifest.json','metrics.json','config.json','output/score_report.json','output/agent.log'].includes(key));
 const source=sourceHref(r.agent_source),config=sourceHref(r.config_source);
 return `<div class="evidence">${links.map(([key,raw])=>`<a href="${esc(extEvidenceHref(raw))}">${esc(key)}</a>`).join('')}${source?`<a href="${esc(source+'/planner.py')}">策略源码</a>`:''}${config?`<a href="${esc(config)}">参数源文件</a>`:''}</div>`;
}
function extScoreCell(r,deltaFirst=false){
 if(!r)return '<td class="numeric extension-score-cell"><span class="subtle">未运行</span></td>';
 const total=extScore(r),d=extDelta(r);
 if(total===null)return `<td class="numeric extension-score-cell"><span class="subtle">${esc(stateNames[r.evaluation_state]||'未取得分数')}</span><span class="run-id">${esc(r.run_id)}</span></td>`;
 const main=deltaFirst?signed(d):fmt(total),minor=deltaFirst?'总分 '+fmt(total):'相对 D Δ '+signed(d);
 return `<td class="numeric extension-score-cell" data-extension-score-run="${esc(r.run_id)}"><b class="${deltaFirst?tone(d):''}">${main}</b><span class="subtle ${deltaFirst?'':tone(d)}">${minor}</span><span class="subtle">required 遗漏 ${fmt(r.required_missing,0)} · J ${fmt(r.coverage_jain,4)}</span><details class="extension-evidence"><summary>分项与证据</summary><p class="run-id">${esc(r.run_id)}</p>${table(['分项','原值'],componentKeys.map(key=>`<tr><th>${componentNames[key]}</th><td class="numeric">${fmt(r.components?.[key])}</td></tr>`).join(''))}<p>${esc(extStageNames[r.declared_stage||r.stage]||r.stage)} · ${esc(stateNames[r.evaluation_state]||r.evaluation_state||'')}<br>观测 ${fmt(r.observe_actions,0)} 次；均长 ${fmt(r.actual_exposure_mean_seconds)} 秒<br>程序耗时 ${fmt(r.runtime_seconds,3)} 秒；pace ${fmt(r.pace_change_count,0)}</p>${extEvidence(r)}</details></td>`;
}
function extGuideBlock(value){
 if(Array.isArray(value))return value.map(item=>typeof item==='string'?textParagraph(item):`<h3>${esc(item.title||item.meaning||item.label||item.id||'')}</h3>${['question','change','why','observed','value','text'].map(key=>textParagraph(item[key])).join('')}`).join('');
 if(value&&typeof value==='object')return (value.question?`<h3>组合试验的问题</h3>${textParagraph(value.question)}`:'')+extGuideBlock(value.design||[])+textParagraph(value.observed)+textParagraph(value.value);
 return textParagraph(value);
}
function renderExtensionGuide(){
 if(EXTG.title)$('extensionTitle').textContent=EXTG.title;
 $('extensionIntro').innerHTML=(EXTG.intro||[]).map(textParagraph).join('')||'<p>第二批结果正在汇总。下方展示已经完成的记录，未运行项目保留为空。</p>';
 $('extensionBaseline').innerHTML=(EXTG.baseline?`<h2>${esc(EXTG.baseline.title||'第二批共同底座')}</h2>${textParagraph(EXTG.baseline.description)}`:'')+textParagraph(EXTG.data_boundary);
 const fields=[['question','想回答什么'],['change','具体改了什么'],['motivation','传统观测动机'],['tradeoff','代价与解释边界'],['observed','观察到的结果'],['iteration','为何迭代或停止'],['value','研究价值']];
 $('extensionStrategyCards').innerHTML=extFamilies.map(f=>{const g=extFamily(f),rs=EXTROWS.filter(r=>r.family===f&&!r.verification_only&&['N2','N3'].includes(r.declared_stage||r.stage)),groups=new Map();for(const r of rs){const key=r.stage+'|'+extCase(r)+'|'+r.config_sha256;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(r);}return `<article class="strategy-explanation" id="extension-family-${f}"><h3>${esc(g.title||f)}<span class="family-code">${f}</span></h3>${fields.map(([key,label])=>g[key]?`<div class="explanation-field"><h4>${label}</h4>${textParagraph(g[key])}</div>`:'').join('')}${!g.change?'<p class="note">解释尚待更新。</p>':''}<div class="extension-strategy-versions"><b>全部开发版本 · 相对 D 增量</b>${[...groups.values()].map(rows=>`<p>${esc(extStageNames[rows[0].stage]||rows[0].stage)} · ${esc(rows[0].variant||extCase(rows[0]))}<br>${extDevCards.map(c=>{const r=rows.find(v=>v.card===c);return `${c} <strong class="${tone(extDelta(r))}">${signed(extDelta(r))}</strong>`;}).join('；')}</p>`).join('')||'<p>开发结果尚未写入。</p>'}</div>${g.frozen_label?textParagraph(g.frozen_label):''}</article>`;}).join('');
 $('extensionCombinationGuide').innerHTML=extGuideBlock(EXTG.combinations);
 $('extensionTakeaways').innerHTML=extGuideBlock(EXTG.takeaways)||'<p class="note">本批总体判断待研究完成后更新。</p>';
 $('extensionHoldoutGuide').innerHTML=extGuideBlock(EXTG.holdout||EXTG.validation||[]);
 const complete=EXTROWS.filter(r=>r.full_season_complete).length,verifications=EXTROWS.filter(r=>r.verification_only).length;
 $('extensionStatus').textContent=`第二批已登记 ${EXTROWS.length} 次运行，其中 ${complete} 次整段完成、${verifications} 次仅作验收；复用参照 ${EXTREFS.length} 条，另列且不算新增试验。${EXT.generated_at_utc?' 数据快照：'+new Date(EXT.generated_at_utc).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})+'（北京时间）。':''}`;
 $('extensionSources').innerHTML=[['第二批讲解','docs/v4-strategy-extension-guide.json'],['第二批 schema','experiments/v4/extension/results/schema.json'],['第二批全部运行','experiments/v4/extension/results/all_runs.json'],['第二批参照 CSV','experiments/v4/extension/results/reference_runs.csv']].map(([label,path])=>`<a href="../${esc(path)}">${label}</a>`).join('')+(EXTG.sources||[]).map(v=>`<a href="${esc(v.url)}">${esc(v.label)}</a>`).join('');
}
function extDevGroups(){
 const stages=['N2','N3','N4'],groups=[];
 for(const stage of stages){const map=new Map();for(const r of EXTROWS.filter(r=>(r.declared_stage||r.stage)===stage&&!r.verification_only&&extDevCards.includes(r.card))){const key=extCase(r)+'|'+r.config_sha256;if(!map.has(key))map.set(key,[]);map.get(key).push(r);}const ordered=[...map.values()].sort((a,b)=>{const rank=f=>extFamilies.includes(f)?extFamilies.indexOf(f):6;return rank(a[0].family)-rank(b[0].family)||extCase(a[0]).localeCompare(extCase(b[0]));});for(const rs of ordered)groups.push({case_id:extCase(rs[0]),stage,rows:rs});}
 return groups;
}
function renderExtensionDevelopment(){
 const groups=extDevGroups(),refs=['D-linear','official-baseline','DTGP-frozen02'].map(id=>({case_id:id,stage:'复用参照',rows:EXTREFS.filter(r=>extCase(r)===id&&extDevCards.includes(r.card))})).filter(g=>g.rows.length),all=[...refs,...groups];
 let lastStage='';const body=all.map(g=>{const heading=lastStage!==g.stage?`<tr class="score-group"><th colspan="5">${esc(extStageNames[g.stage]||g.stage)}${g.stage==='复用参照'?' · 不计为新增试验':''}</th></tr>`:'';lastStage=g.stage;const rs=extDevCards.map(c=>g.rows.filter(r=>r.card===c)),avg=mean(rs.map(rows=>rows.length===1?extDelta(rows[0]):null));return heading+`<tr><th>${esc(extLabel(g.case_id,g.rows[0]))}<span class="subtle">${esc(g.case_id)}</span></th><td>${esc(extStageNames[g.stage]||g.stage)}</td>${rs.map(rows=>rows.length<=1?extScoreCell(rows[0]):`<td>${rows.map(r=>`<p>${esc(r.run_id)}：${fmt(extScore(r))}；Δ ${signed(extDelta(r))}</p>${extEvidence(r)}`).join('')}</td>`).join('')}<td class="numeric ${tone(avg)}">${signed(avg)}<span class="subtle">两卡等权；缺一卡则留空</span></td></tr>`;}).join('');
 $('extensionDevelopmentMatrix').innerHTML=table(['方案 / 具体版本','阶段','demo 总分与 ΔD','dev-season 总分与 ΔD','开发平均 ΔD'],body||'<tr><td colspan="5">开发记录尚未取得，空值不代表零分。</td></tr>','score-overview-table extension-matrix');
 $('extensionDevelopmentMatrix').dataset.configurationCount=groups.length;
}
function extFrozenCases(){
 const declared=EXTG.frozen_cases||EXTG.freeze?.cases||[],ids=[...new Set(EXTROWS.filter(r=>(r.declared_stage||r.stage)==='N5').map(extCase))];
 if(declared.length){const chosen=declared.map(v=>({case_id:v.case_id||v.id,label:v.label,development_case_id:v.development_case_id}));for(const id of ids)if(!chosen.some(v=>v.case_id===id))chosen.push({case_id:id});return chosen;}
 return ids.map(id=>({case_id:id}));
}
function extFrozenRow(id,card){return EXTROWS.find(r=>(r.declared_stage||r.stage)==='N5'&&extCase(r)===id&&r.card===card);}
function extFrozenSummary(id){
 const rs=extHoldCards.map(c=>extFrozenRow(id,c)),available=rs.filter(r=>r?.full_season_complete&&extScore(r)!==null&&extDelta(r)!==null).length;
 return {available,averageDelta:available===4?mean(rs.map(extDelta)):null,wins:available===4?rs.filter(r=>extDelta(r)>0).length:null};
}
function extFrozenDevelopment(spec){
 const id=spec.development_case_id||spec.case_id,reused=['official-baseline','D-linear','DTGP-frozen02'].includes(id),stage=reused?'复用参照':id.split('+').length>2?'N4':'N2';
 const pool=reused?EXTREFS:EXTROWS.filter(r=>(r.declared_stage||r.stage)===stage&&!r.verification_only),matches=extDevCards.map(c=>pool.filter(r=>extCase(r)===id&&r.card===c)),rs=matches.map(rows=>rows.length===1?rows[0]:null),available=rs.filter(r=>r?.full_season_complete&&extScore(r)!==null&&extDelta(r)!==null).length;
 return {case_id:id,stage,available,run_ids:rs.filter(Boolean).map(r=>r.run_id),averageDelta:available===2?mean(rs.map(extDelta)):null};
}
function renderExtensionHoldout(){
 const specs=extFrozenCases(),deltaFirst=$('extensionHoldoutDelta').checked,rows=EXTROWS.filter(r=>(r.declared_stage||r.stage)==='N5'&&extHold(r.card)),complete=rows.filter(r=>r.full_season_complete).length;
 $('extensionHoldoutStatus').textContent=specs.length?`冻结方案 ${specs.length} 个 × 四张新保留卡；已取得 ${rows.filter(r=>extScore(r)!==null).length} 个分数，${complete} 个整段完成。开封后不再按结果调参。`:'四张新保留卡仍封存，冻结方案清单尚未登记。N5 未运行；不以开发成绩代填保留成绩。';
 $('extensionTransferOverview').innerHTML=table(['方案','开发平均 ΔD','新卡平均 ΔD','胜过 D'],specs.map(spec=>{const d=extFrozenDevelopment(spec),h=extFrozenSummary(spec.case_id);return `<tr data-extension-transfer-case="${esc(spec.case_id)}"><th>${esc(spec.label||extLabel(spec.case_id))}</th><td class="numeric ${tone(d.averageDelta)}">${signed(d.averageDelta)}</td><td class="numeric ${tone(h.averageDelta)}">${signed(h.averageDelta)}</td><td class="numeric">${h.wins===null?'—':h.wins+'/4'}</td></tr>`;}).join('')||'<tr><td colspan="4">冻结方案待登记；未运行不填零。</td></tr>','extension-transfer-table');
 $('extensionTransferOverview').dataset.configurationCount=specs.length;
 const body=specs.map(spec=>{const example=extHoldCards.map(c=>extFrozenRow(spec.case_id,c)).find(Boolean),summary=extFrozenSummary(spec.case_id),development=extFrozenDevelopment(spec),pending=summary.available===4?'四卡等权':`${summary.available}/4 已齐；暂不计算`;return `<tr data-extension-case="${esc(spec.case_id)}"><th>${esc(spec.label||extLabel(spec.case_id,example))}<span class="subtle">N5 冻结 · ${esc(spec.case_id)}</span>${spec.development_case_id?`<span class="subtle">开发版本 ${esc(spec.development_case_id)}</span>`:''}</th>${extHoldCards.map(c=>extScoreCell(extFrozenRow(spec.case_id,c),deltaFirst)).join('')}<td class="numeric extension-summary-cell ${tone(development.averageDelta)}"><b>${signed(development.averageDelta)}</b><span class="subtle">${esc(extStageNames[development.stage]||development.stage)} · ${development.available===2?'两卡等权':development.available+'/2 已齐；暂不计算'}</span></td><td class="numeric extension-summary-cell ${tone(summary.averageDelta)}"><b>${signed(summary.averageDelta)}</b><span class="subtle">${pending}</span></td><td class="numeric extension-wins-cell"><b>${summary.wins===null?'—':summary.wins+'/4'}</b><span class="subtle">${summary.wins===null?'四卡齐后计算':'严格 ΔD > 0'}</span></td></tr>`;}).join('')||'<tr><th>冻结方案待登记</th>'+extHoldCards.map(()=>'<td class="numeric"><span class="subtle">未运行（封存）</span></td>').join('')+'<td class="numeric">—</td><td class="numeric">—</td><td class="numeric">—</td></tr>';
 $('extensionHoldoutMatrix').innerHTML=table(['N5 冻结方案',...extHoldCards.map(c=>`${c}<span class="subtle">新生成保留卡</span>`),'开发平均 ΔD','保留平均 ΔD','胜过 D 卡数'],body,'score-overview-table extension-holdout-matrix');
 renderExtensionHoldoutCharts(specs);
 $('extensionHoldoutMatrix').dataset.configurationCount=specs.length;
}
function renderExtensionHoldoutCharts(specs=extFrozenCases()){
 $('extensionHoldoutCharts').innerHTML=extHoldCards.map(c=>`<article class="official-chart"><h3>${esc(c)} · 相对同卡 D</h3><svg id="extensionChart-${c}" role="img" aria-label="${esc(c)}各冻结方案相对D分差"></svg><p class="note" id="extensionChartNote-${c}"></p></article>`).join('');
 for(const c of extHoldCards){const items=specs.map(spec=>{const r=extFrozenRow(spec.case_id,c);return {label:spec.label||spec.case_id,value:extDelta(r)};}).filter(v=>v.value!==null);if(items.length){bars('extensionChart-'+c,items);$('extensionChartNote-'+c).textContent='Δ = 冻结方案 − 同卡 D；未取得分数或参照的方案不绘条形。完整数值与分项在上表。';}else{$('extensionChart-'+c).setAttribute('hidden','');$('extensionChartNote-'+c).textContent='相对 D 分差尚未取得，不绘制零分或空条。';}}
}
function renderExtensionRuns(){
 $('extensionRunCount').textContent=`本批 ${EXTROWS.length} 条运行记录全部保留；验收 ${EXTROWS.filter(r=>r.verification_only).length} 条单独标注。复用的 ${EXTREFS.length} 条旧参照列在开发总览，不计为新增实验。`;
 $('extensionRunTable').innerHTML=table(['运行 / 参数','阶段 / 类别','卡片','总分 / ΔD','科学分','required / J','观测 / 均长秒','程序秒 / pace','完成 / 证据'],EXTROWS.map(r=>`<tr><td><b class="run-id">${esc(r.run_id)}</b><span class="subtle">${esc(extCase(r))}</span></td><td>${esc(extStageNames[r.declared_stage||r.stage]||r.stage)}<span class="badge ${r.verification_only?'control':''}">${r.verification_only?'等价验收':r.intentional_timeout?'故意 timeout guard':'策略评估'}</span></td><td>${esc(r.card)}<span class="subtle">${extHold(r.card)?'新保留':'开发'}</span></td><td class="numeric">${fmt(extScore(r))}<span class="subtle ${tone(extDelta(r))}">${signed(extDelta(r))}</span></td><td class="numeric">${fmt(r.components?.sum_best_scores)}</td><td class="numeric">${fmt(r.required_missing,0)} / ${fmt(r.coverage_jain,4)}</td><td class="numeric">${fmt(r.observe_actions,0)} / ${fmt(r.actual_exposure_mean_seconds)}</td><td class="numeric">${fmt(r.runtime_seconds,3)} / ${fmt(r.pace_change_count,0)}</td><td>${esc(stateNames[r.evaluation_state]||r.evaluation_state||'')}<details><summary>原始证据</summary>${extEvidence(r)}<pre>${esc(JSON.stringify(r.config,null,2))}</pre></details></td></tr>`).join('')||'<tr><td colspan="9">本批运行记录尚未取得。</td></tr>','extension-record-table');
}
function initExtension(){
 renderExtensionGuide();renderExtensionDevelopment();renderExtensionHoldout();renderExtensionRuns();
 $('extensionHoldoutDelta').addEventListener('change',renderExtensionHoldout);
 $('downloadExtensionJson').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(EXT,null,2)+'\n'],{type:'application/json;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='extension-all_runs.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
 let timer,observedWidth;new ResizeObserver(entries=>{const width=entries[0]?.contentRect.width;if(typeof width!=='number'||width===observedWidth)return;const initial=observedWidth===undefined;observedWidth=width;if(initial)return;clearTimeout(timer);timer=setTimeout(renderExtensionHoldoutCharts,100);}).observe($('extension-holdout'));
 window.study.extension={rowCount:EXTROWS.length,referenceCount:EXTREFS.length,delta:extDelta,score:extScore,reference:extReference,developmentGroups:extDevGroups,frozenCases:extFrozenCases,frozenRow:extFrozenRow,frozenSummary:extFrozenSummary,frozenDevelopment:extFrozenDevelopment,renderHoldout:renderExtensionHoldout};
}
initExtension();
