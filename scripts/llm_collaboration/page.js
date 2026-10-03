'use strict';
const DOC = JSON.parse(document.getElementById('document-data').textContent);
const $ = id => document.getElementById(id);
const value = id => Number($(id).value);
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num = (n, digits = 2) => Number(n).toFixed(digits);

function renderEvidence() {
  const limit = Math.ceil(Math.max(...DOC.evidence.flatMap(d => [d.dev, d.holdout])) / 100) * 100;
  $('evidence-chart').innerHTML = DOC.evidence.map(d => `<div class="evidence-row"><div class="evidence-label">${esc(d.name)}<small>${esc(d.meaning)}</small></div><div class="bar-pair"><div class="value-bar" title="开发平均增量 ${num(d.dev)}"><i style="width:${d.dev/limit*100}%"></i><b>开发 +${num(d.dev)}</b></div><div class="value-bar holdout" title="保留平均增量 ${num(d.holdout)}"><i style="width:${d.holdout/limit*100}%"></i><b>保留 +${num(d.holdout)}</b></div></div></div>`).join('');
}

let currentStep = 0;
DOC.scenarios.forEach((row, i) => {
  const option = document.createElement('option');
  option.value = String(i);
  option.textContent = row[0];
  $('scenario-select').appendChild(option);
});

function flowDetail(step, scenario, enabled) {
  const type = Number(scenario);
  if (step === 0) return '环境给出本轮快照。程序只处理已发布的信息；初始化消息没有动作回复。';
  if (step === 1) return '状态账本由程序维护。目标最高有效贡献、完成情况的估计与依据分别记录；饱和和 program 歧义不能被忽略。';
  if (step === 2) {
    if (!enabled) return '当前关闭模型接入。本轮由程序诊断和规划，不发起模型请求。';
    if (type === 0) return '普通回合没有新的决策缺口。即使允许接入 LLM，本轮也不调用。';
    if (type === 3) return '本情景模拟一次咨询失败。程序检查时限和剩余预算，超时后停止等待。';
    return DOC.scenarios[type][2] + '。程序整理问题和预算，只在需要判断的节点咨询。';
  }
  if (step === 3) return type === 2
    ? '除常规科学观测外，程序加入换方向探测、继续观察和报告等可适用方案，计算合法性与时间代价。'
    : '程序保留不同动机的方案，分别给出科学收益、必做门槛、请求和剩余窗口的估计后果。不能只给三个相似的最高分候选。';
  if (step === 4) {
    if (!enabled || type === 0) return '当前不调用模型。程序依照现有规划选择方案；这也是正常回合的主要路径。';
    if (type === 3) return '演示模型没有及时给出有效建议。没有收到的判断不能被当作批准，旧建议也不能直接沿用。';
    if (type === 1) return '模型比较短期计划，说明哪些机会更紧迫，提出有效期与重新评估条件。此例不预设哪组必然胜出。';
    return '模型保留天气、方向干扰、效率下降和估计失准等解释，选择有区分能力的下一项验证。证据不足时应先探测。';
  }
  if (step === 5) return (enabled && type !== 0)
    ? DOC.scenarios[type][4] + '。程序可以验证可检查的条件，不能保证未来天气或真实收益。'
    : '检查当前目标、光纤、曝光时长、全程最低高度和协议序号。程序方案同样需要经过这些检查。';
  if (step === 6) return '只提交一个当前动作。模型建议不会绕过程序直接发到比赛环境，也不会预先提交未来轮次。';
  return '环境执行后才交回控制权。程序将实际结果与估计比较；出现计划失效条件时，后续回合再决定是否咨询。';
}

function renderFlow() {
  const scenario = value('scenario-select');
  const enabled = $('llm-enabled').checked;
  const modelUsed = enabled && scenario !== 0;
  const row = DOC.steps[currentStep];
  $('scenario-evidence').textContent = '当前证据：' + DOC.scenarios[scenario][1];
  $('decision-stepper').innerHTML = DOC.steps.map((s, i) => `<button type="button" data-step="${i}" aria-pressed="${i===currentStep}" class="${i===currentStep?'is-active ':''}${i===4&&modelUsed?'llm-step':''}"><span>${String(i+1).padStart(2,'0')}</span>${esc(s[0].replace(/^\d+\s*/,''))}</button>`).join('');
  const activeModel = currentStep === 4 && modelUsed && scenario !== 3;
  $('flow-readout').classList.toggle('model-active', activeModel);
  const role = activeModel ? 'LLM 参与 · 程序提供候选与证据' : '固定程序负责';
  const output = currentStep === 4 && (!modelUsed || scenario === 3)
    ? (scenario === 3 && enabled ? '无有效模型建议，进入程序回退' : '程序选择的本轮方案')
    : row[4];
  $('flow-readout').innerHTML = `<span class="ownership">${role}</span><h4>${esc(row[0])}</h4><p class="readout-detail">${esc(flowDetail(currentStep, scenario, enabled))}</p><div class="readout-grid"><div><strong>本步输入</strong>${esc(row[3])}</div><div><strong>本步输出</strong>${esc(output)}</div></div><p class="readout-emphasis">${esc(currentStep===4&&modelUsed?DOC.scenarios[scenario][3]:row[1])}</p>`;
  $('step-position').textContent = `第 ${currentStep+1} / ${DOC.steps.length} 步 · ${DOC.scenarios[scenario][0]}`;
  $('step-prev').disabled = currentStep === 0;
  $('step-next').textContent = currentStep === DOC.steps.length-1 ? '下一轮：第一步' : '下一步';
}
$('decision-stepper').addEventListener('click', event => {
  const button = event.target.closest('button[data-step]');
  if (!button) return;
  currentStep = Number(button.dataset.step);
  renderFlow();
  $('decision-stepper').querySelector(`[data-step="${currentStep}"]`).focus({preventScroll:true});
});
$('step-next').addEventListener('click', () => {currentStep = (currentStep+1)%DOC.steps.length; renderFlow();});
$('step-prev').addEventListener('click', () => {currentStep = Math.max(0,currentStep-1); renderFlow();});
$('flow-reset').addEventListener('click', () => {currentStep=0; renderFlow();});
$('scenario-select').addEventListener('change', renderFlow);
$('llm-enabled').addEventListener('change', renderFlow);

function completionFactor(flux, seconds, quality, minimumAltitude) {
  return minimumAltitude < DOC.reference.minimumAltitude ? 0 : Math.min(flux*seconds*quality/DOC.reference.f0t0, 1);
}
function renderExposure() {
  const f=value('flux'), q=value('quality'), t=value('duration'), h=value('altitude');
  $('flux-value').textContent=num(f);
  $('quality-value').textContent=num(q);
  $('duration-value').textContent=t+' 秒';
  $('altitude-value').textContent=h+'°';
  const g=completionFactor(f,t,q,h);
  const legal=h>=DOC.reference.minimumAltitude;
  const required=Math.ceil(DOC.reference.threshold*DOC.reference.f0t0/(f*q));
  const practical=Math.max(60,required);
  const reachable=legal&&practical<=DOC.reference.maximumExposure;
  const done=legal&&g>=DOC.reference.threshold;
  for(const id of ['once','twice']){
    $('factor-'+id).style.width=g*100+'%';
    $('factor-'+id+'-value').textContent=num(g,3);
  }
  $('minimum-duration').textContent=legal?practical+' 秒':'几何无效';
  $('threshold-reachable').textContent=reachable?'可达标':'不可达标';
  $('threshold-status').textContent=done?'已达标':'未达标';
  $('exposure-explanation').classList.toggle('alert', !legal || !reachable);
  $('exposure-explanation').textContent=!legal
    ? `全程最低高度 ${h}° 低于参考门槛 ${DOC.reference.minimumAltitude}°，该源整次曝光无效；延长时间不能补救。`
    : !reachable
      ? `在 f=${num(f)}、Q=${num(q)} 的假设下，估计需 ${required} 秒，超过参考最大时长 ${DOC.reference.maximumExposure} 秒。本次允许时长内无法达标。`
      : `单次 g=${num(g,3)}，两次相同曝光仍是 ${num(g,3)}，不会相加。估计至少 ${practical} 秒才能达到 ${DOC.reference.threshold}；真实调度还要检查窗口和估计误差。`;
}
for(const id of ['flux','quality','duration','altitude'])$(id).addEventListener('input',renderExposure);
$('exposure-reset').addEventListener('click',()=>{
  for(const [id,val]of Object.entries({flux:.2,quality:1,duration:450,altitude:60}))$(id).value=val;
  renderExposure();
});

function comparePlans(count, futureOpportunity) {
  const penalty = futureOpportunity ? 0 : count*DOC.reference.penalty;
  return {a:40-penalty,b:25,penalty};
}
function renderTradeoff(){
  const count=value('saved'), future=$('future-opportunity').checked;
  const s=comparePlans(count,future);
  $('saved-value').textContent=count+' 个';
  $('plan-a-score').textContent=s.a+' 分';
  $('plan-b-score').textContent=s.b+' 分';
  $('plan-a-math').textContent=future?'暂按40科学分比较，不把未来罚分确定化':`40 科学分 − ${s.penalty} 永久遗漏罚分`;
  $('plan-b-math').textContent='25 科学分；本例这组必做源已完成';
  $('plan-a').classList.toggle('selected',s.a>s.b);
  $('plan-b').classList.toggle('selected',s.b>s.a);
  $('tradeoff-explanation').textContent=future
    ? '后续仍有机会时，不能把整项50分罚款都算作现在选择 B 的独占收益。本例暂按当前科学分，A 较高；实际要继续估计后续完成概率与机会成本。'
    : count===0
      ? '没有必做完成差异时，本例 A 的40分高于 B 的25分。'
      : `假设这组 ${count} 个目标本次跳过就会永久遗漏，A 的两项净贡献为 ${s.a} 分，B 为 ${s.b} 分。B 虽少15科学分，却避免 ${s.penalty} 分罚款。`;
}
$('saved').addEventListener('input',renderTradeoff);
$('future-opportunity').addEventListener('change',renderTradeoff);

function budgetEstimate(calls, latency, base){
  const model=calls*latency,total=base+model,left=DOC.reference.wallclock-total;
  return{model,total,left};
}
function renderBudget(){
  const calls=value('calls'),latency=value('latency'),base=value('base-time');
  const s=budgetEstimate(calls,latency,base);
  $('calls-value').textContent=calls+' 次';
  $('latency-value').textContent=latency+' 秒';
  $('base-time-value').textContent=base+' 秒';
  const remaining=Math.max(0,s.left),divisor=Math.max(DOC.reference.wallclock,s.total);
  for(const [id,seconds]of [['base',base],['model',s.model],['left',remaining]])$('budget-'+id).style.width=seconds/divisor*100+'%';
  $('model-seconds').textContent=s.model+' 秒';
  $('total-seconds').textContent=s.total+' 秒';
  $('left-seconds').textContent=s.left>=0?s.left+' 秒':'超出 '+(-s.left)+' 秒';
  $('budget-explanation').classList.toggle('alert',s.left<0 || s.model>90);
  $('budget-explanation').textContent=s.left<0
    ? `按本例输入已超出900秒 ${-s.left} 秒。需要减少咨询、缩短等待或降低其他耗时；模拟时间不推进，也不能停止真实计时。`
    : s.model>90
      ? `模型等待为 ${s.model} 秒，超过本文建议作为起点的90秒研究预算。虽然本例总耗时仍低于900秒，也需为尾部延迟和平台开销留余量。`
      : `模型等待 ${s.model} 秒，其他处理 ${base} 秒，合计 ${s.total} 秒。本例尚余 ${s.left} 秒；这是构造预算，不是运行时完成保证。`;
}
for(const id of ['calls','latency','base-time'])$(id).addEventListener('input',renderBudget);

$('download-markdown').addEventListener('click',()=>{
  const url=URL.createObjectURL(new Blob([DOC.markdown],{type:'text/markdown;charset=utf-8'}));
  const anchor=document.createElement('a');
  anchor.href=url;anchor.download='v4-llm-collaboration.md';document.body.appendChild(anchor);anchor.click();anchor.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
});

if('IntersectionObserver' in window){
  const observer=new IntersectionObserver(entries=>{
    const visible=entries.filter(e=>e.isIntersecting).sort((a,b)=>a.boundingClientRect.top-b.boundingClientRect.top);
    if(!visible.length)return;
    document.querySelectorAll('.sidebar nav a').forEach(a=>a.classList.toggle('active',a.getAttribute('href')==='#'+visible[0].target.id));
  },{rootMargin:'-10% 0px -55% 0px',threshold:0});
  document.querySelectorAll('.doc-section').forEach(s=>observer.observe(s));
}
renderEvidence();renderFlow();renderExposure();renderTradeoff();renderBudget();
