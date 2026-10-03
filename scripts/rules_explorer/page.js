'use strict';
const data=JSON.parse(document.getElementById('rules-data').textContent),score=data.score;
const el=id=>document.getElementById(id),value=id=>Number(el(id).value);
const fmt=(n,p=3)=>Number(n).toFixed(p);
function slot(){
 const start=value('slot-start'),requested=value('slot-duration'),nightEnd=5400,end=Math.min(start+requested,nightEnd),actual=end-start;
 const points=[];for(let i=900;i<nightEnd;i+=900)if(i>start&&i<=end)points.push(i);
 el('slot-start-value').textContent=start;el('slot-duration-value').textContent=requested;
 el('slot-actual').textContent=actual+' 秒';el('slot-boundaries').textContent=points.length+' 个';el('slot-next').textContent='开夜后 '+end+' 秒';
 const x=t=>35+t/5400*790;
 let svg='<line x1="35" y1="65" x2="825" y2="65" stroke="#9ebcb0" stroke-width="2"/>';
 for(let i=0;i<=5400;i+=900)svg+=`<line x1="${x(i)}" y1="25" x2="${x(i)}" y2="115" stroke="${i===5400?'#a65e09':'#b5cbc2'}" stroke-dasharray="${i===5400?'0':'5 4'}"/><text x="${x(i)}" y="138" text-anchor="middle">${i===5400?'5400 夜末':i+'s'}</text>`;
 svg+=`<rect x="${x(start)}" y="52" width="${Math.max(3,x(end)-x(start))}" height="27" rx="3" fill="#0a8276"/><circle cx="${x(start)}" cy="65" r="5" fill="#084c41"/><circle cx="${x(end)}" cy="65" r="6" fill="#ba7a0d"/><text x="${Math.max(70,x(start))}" y="16" text-anchor="middle">开始 ${start}s</text><text x="${Math.min(750,x(end))}" y="104" text-anchor="middle">交回控制权 ${end}s</text>`;
 el('slot-timeline').innerHTML=svg;
 el('slot-explanation').textContent=(actual<requested?`夜末将${requested}秒申报截为${actual}秒，按实际时长计分。`:`${requested}秒曝光完整执行，经过${points.length}个普通边界。`)+`内部切换天气并积分，中途不产生Agent请求。到${end}秒后才生成下轮快照，期间已发布消息一起送达。这里假设还有后续观测夜；若巡天全部结束，则进入终局结算。`;
}
function quality(){
 const alt=value('q-alt'),eta=value('q-eta'),direction=value('q-direction'),closed=el('q-closed').checked;
 const norm=1+.50572*Math.pow(96.07995,-1.6364),X=norm/(Math.sin(alt*Math.PI/180)+.50572*Math.pow(alt+6.07995,-1.6364));
 const beta=score.airmass_exponent,q0=score.q0,B=.8*.8/(Math.pow(X,beta)*q0),Q=B*eta*direction*(closed?0:1);
 el('q-alt-value').textContent=alt+'°';el('q-eta-value').textContent=fmt(eta,2);el('q-direction-value').textContent=fmt(direction,2);
 el('q-quality').textContent=fmt(Q);el('q-band').textContent=fmt(B);
 const bands=score.program.bands;const band=B>=bands.DARK?'DARK':B>=bands.BRIGHT?'BRIGHT':'BACKUP';el('q-program').textContent=band;
 el('q-explanation').textContent=`X=${fmt(X)}。本例Q随η、方向乘数和目标方向关闭改变，B只随共同天气与几何改变；仅目标方向关闭会令Q=0，B仍为${fmt(B)}。当前显示的是恒定条件演示，真实曝光按slot与事件分段。`;
}
function settlement(){
 const g1=value('ledger-g1'),g2=value('ledger-g2'),loss=el('ledger-loss').checked,m=score.program.multipliers.DARK,mismatch=score.program.mismatch_multiplier;
 const c1=1.7*g1*m,c2=1.7*g2*mismatch,best=loss?c1:Math.max(c1,c2),factor=loss?g1:Math.max(g1,g2),threshold=score.required.observed_factor_threshold;
 el('ledger-g1-value').textContent=fmt(g1,2);el('ledger-g2-value').textContent=fmt(g2,2);
 el('ledger-best').textContent=fmt(best);el('ledger-factor').textContent=fmt(factor,2);el('ledger-required').textContent=factor>=threshold?'达标':'未达标';
 el('ledger-explanation').textContent=`第一次贡献${fmt(c1)}，第二次贡献${fmt(c2)}${loss?'已撤销':''}。最高贡献为${fmt(best)}；最大完成因子为${fmt(factor,2)}，两次g不相加。required按g≥${threshold}检查，program倍率不改变门槛。`;
}
const explanations=[
 '首轮last_result为空；首公告和首预报同时出现在latest快照与new_messages批次，不要重复计入。',
 '这是1800秒曝光结束后的唯一下一轮请求：new_messages积累了两条bulletin，latest_bulletin只指向最新一条，last_result对应整次observe。',
 '只剩30秒却申报60秒，now已经到该夜夜末；last_result没有实际时长字段，需要结合上一轮起点与夜历核对。',
 'report不推进now，但decision_sequence递增。相同结果同时出现在last_result与report_result内，奖惩不能算两次。'
];
function message(){const i=value('message-select');el('message-json').textContent=JSON.stringify(data.messages[i].value,null,2);el('message-explanation').textContent=explanations[i];}
for(const [i,item]of data.messages.entries()){const option=document.createElement('option');option.value=i;option.textContent=item.name;el('message-select').append(option);}
el('message-select').addEventListener('change',message);
for(const id of ['slot-start','slot-duration'])el(id).addEventListener('input',slot);
for(const id of ['q-alt','q-eta','q-direction','q-closed'])el(id).addEventListener('input',quality);
for(const id of ['ledger-g1','ledger-g2','ledger-loss'])el(id).addEventListener('input',settlement);
el('slot-cross-example').addEventListener('click',()=>{el('slot-start').value=450;el('slot-duration').value=1800;slot();});
el('slot-night-example').addEventListener('click',()=>{el('slot-start').value=5370;el('slot-duration').value=60;slot();});
el('nav-toggle').addEventListener('click',()=>{const open=el('sidebar').classList.toggle('open');el('nav-toggle').textContent=open?'收起目录':'展开目录';});
el('download-rules').addEventListener('click',()=>{const source=data.markdown[0],url=URL.createObjectURL(new Blob([source.text],{type:'text/markdown;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download=source.name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
slot();quality();settlement();message();
