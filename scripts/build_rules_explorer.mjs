#!/usr/bin/env node
// 规则和源码解读都来自Markdown；此文件只负责展现与控件。
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
let marked;try{({marked}=await import('marked'));}catch{const modules=process.env.SURVEY_DOC_MODULES||'/Users/cxjh168/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';({marked}=await import(pathToFileURL(path.join(modules,'marked/lib/marked.esm.js')).href));}
const digest=s=>createHash('sha256').update(s).digest('hex');
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const settings=JSON.parse(fs.readFileSync(path.join(root,'experiments/current/environment.json')));
const score=JSON.parse(fs.readFileSync(path.join(root,settings.cards,'L1/config/v4_score_config.json')));
const sources=['v4-rules-and-protocol.md','python-source-map.md'].map(name=>({name,markdown:fs.readFileSync(path.join(root,'docs',name),'utf8')}));
const readCase=name=>JSON.parse(fs.readFileSync(path.join(root,'experiments/current/rules-audit/evidence-refresh',name,'public_requests.json')));
const cross=readCase('cross-slot'),night=readCase('night-end'),report=readCase('report-limit');
const messages=[
 {name:'开场：第一条request',value:cross[0]},
 {name:'跨slot：整次结束后一次送达',value:cross[2]},
 {name:'夜末：实际30秒后的request',value:night[2]},
 {name:'举报：新序号、同一模拟时刻',value:report[1]}
];
const widgets={
 slot:`<div class="interactive" id="slot-widget"><span class="badge">TIME BOUNDARIES · 构造时间轴</span><h3>移动起点与时长，观察控制权何时回来</h3><p class="hint">演示一夜5400秒，slot为900秒；只展示时间规则，省略目标几何和天气事件。普通边界虚线不会触发Agent回调。</p><div class="controls"><label>起点距开夜 / 秒 <output id="slot-start-value"></output><input type="range" id="slot-start" min="0" max="5370" step="30" value="450"></label><label>申报曝光 / 秒 <output id="slot-duration-value"></output><input type="range" id="slot-duration" min="60" max="3600" step="30" value="1800"></label></div><svg class="timeline" id="slot-timeline" viewBox="0 0 860 150" role="img" aria-label="曝光跨slot时间轴"></svg><div class="metrics"><div><span>实际曝光</span><strong id="slot-actual"></strong></div><div><span>经过的普通边界</span><strong id="slot-boundaries"></strong></div><div><span>下次交回控制权</span><strong id="slot-next"></strong></div></div><p class="result" id="slot-explanation" aria-live="polite"></p><div class="actions"><button id="slot-cross-example">看跨两个slot</button><button id="slot-night-example">看夜末只剩30秒</button></div></div>`,
 quality:`<div class="interactive" id="quality-widget"><span class="badge">QUALITY · 恒定条件演示</span><h3>改变效率与方向关闭，分别看Q与B</h3><p class="hint">使用L1公开q0/β/program配置。构造常数τ=.8、K=.8、s=1、L=1；方向影响为单独乘数。不是天气预测，也不替代真实分段积分。</p><div class="controls"><label>高度 / 度 <output id="q-alt-value"></output><input id="q-alt" type="range" min="30" max="90" value="60"></label><label>仪器效率η <output id="q-eta-value"></output><input id="q-eta" type="range" min="0" max="1.5" step=".05" value="1"></label><label>方向质量乘数 <output id="q-direction-value"></output><input id="q-direction" type="range" min="0" max="1" step=".05" value="1"></label><label class="switch"><input id="q-closed" type="checkbox">仅目标方向关闭</label></div><div class="metrics"><div><span>完成质量Q</span><strong id="q-quality"></strong></div><div><span>判档质量B</span><strong id="q-band"></strong></div><div><span>实际program档位</span><strong id="q-program"></strong></div></div><p class="result" id="q-explanation" aria-live="polite"></p></div>`,
 settlement:`<div class="interactive" id="settlement-widget"><span class="badge">LEDGER · 两次构造曝光</span><h3>最好分与最高完成因子，可以来自不同曝光</h3><div class="controls"><label>第一次g <output id="ledger-g1-value"></output><input id="ledger-g1" type="range" min="0" max="1" step=".05" value=".8"></label><label>第二次g <output id="ledger-g2-value"></output><input id="ledger-g2" type="range" min="0" max="1" step=".05" value=".9"></label><label class="switch"><input id="ledger-loss" type="checkbox">模拟resync撤销第二次曝光</label></div><p class="hint">w=1.7；第一次匹配DARK，第二次声明不匹配。这里只比较一个源，未加入请求、覆盖和report奖惩。</p><div class="metrics"><div><span>最高贡献best_score</span><strong id="ledger-best"></strong></div><div><span>最大完成因子max_factor</span><strong id="ledger-factor"></strong></div><div><span>required是否达标</span><strong id="ledger-required"></strong></div></div><p class="result" id="ledger-explanation" aria-live="polite"></p></div>`,
 messages:`<div class="interactive" id="messages-widget"><span class="badge">PROTOCOL · 官方引擎实测公开消息</span><h3>展开实际收到的一条消息</h3><label>验证情景<select id="message-select" aria-label="验证情景"></select></label><p class="result" id="message-explanation" aria-live="polite"></p><div class="message-layout"><pre id="message-json" tabindex="0" aria-label="公开JSON消息"></pre></div><p class="hint">四个情景均为本轮脚本验证输出。空分配只用来核对时间边界；消息未包含天气真值、未来卡文件或密钥。字段含义按下方完整字典阅读。</p></div>`
};
const diagrams=[];const headings=[];
function render(source,index){
 let html=marked.parse(source.markdown,{gfm:true}).replace(/^<h1>[\s\S]*?<\/h1>\s*/,'');
 html=html.replace(/<!-- interactive:([a-z]+) -->/g,(_,key)=>{if(!widgets[key])throw Error(key);return widgets[key];});
 html=html.replace(/<p><img src="(\.?\/?diagrams\/[^" ]+\.svg)" alt="([^"]*)"\s*\/?><\/p>/g,(_,relative,alt)=>{
  const file=path.join(root,'docs',relative),mmd=fs.readFileSync(file.replace(/\.svg$/,'.mmd'),'utf8'),svg=fs.readFileSync(file,'utf8');
  if(!svg.includes(`data-document-diagrams-source-sha256="${digest(mmd)}"`))throw Error('Stale diagram: '+relative);
  diagrams.push({source:path.relative(root,file.replace(/\.svg$/,'.mmd')),sha256:digest(mmd)});
  const offline=svg.replace(/@import\s+url\([^)]*\)\s*;/g,'');
  return `<details class="diagram"><summary>查看图：${alt}</summary><figure aria-label="${alt}">${offline}</figure></details>`;
 });
 html=html.replace(/<table>([\s\S]*?)<\/table>/g,'<div class="table-scroll" tabindex="0"><table>$1</table></div>');
 const pieces=html.split(/(?=<h2>)/),intro=pieces.shift();
 const sections=pieces.map((piece,i)=>{const title=piece.match(/^<h2>([\s\S]*?)<\/h2>/)[1];const id=`doc-${index}-${i}`;headings.push({id,title:title.replace(/^\d+\.\s*/,''),group:index});return `<section class="section" id="${id}"><div class="number">${index?'PYTHON':'V4'} / ${String(i+1).padStart(2,'0')}</div>${piece}</section>`;}).join('\n');
 return `<div class="intro">${intro}</div>${sections}`;
}
const body=sources.map(render);
const data={upstream_commit:settings.upstream_commit,score,messages,markdown:sources.map(s=>({name:s.name,text:s.markdown}))};
const css=fs.readFileSync(path.join(root,'scripts/rules_explorer/page.css'),'utf8'),js=fs.readFileSync(path.join(root,'scripts/rules_explorer/page.js'),'utf8');
const html=`<!doctype html><html lang="zh-CN" data-source-sha256="${digest(sources.map(s=>s.markdown).join('\n'))}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>v4规则与Python交互讲解</title><style>${css}</style></head><body><a class="skip" href="#main">跳到正文</a><aside id="sidebar"><a class="brand" href="#top">巡天 Agent<small>v4 · 规则与源码</small></a><button class="mobile-nav" id="nav-toggle">展开目录</button><nav aria-label="章节目录">${[0,1].map(group=>`<h3>${group?'Python源码理解':'正式v4规则'}</h3>${headings.filter(h=>h.group===group).map(h=>`<a href="#${h.id}">${h.title}</a>`).join('')}`).join('')}</nav><div class="nav-foot">核对 · 2026.10.03<br>源码 · ${settings.upstream_commit.slice(0,7)}<br><a href="README.md">文档与session入口 ↗</a></div></aside><main id="main"><header id="top"><div class="eyebrow">OBSERVATION · DECISION · SETTLEMENT</div><h1>从一次曝光，<br>看懂整轮交互。</h1><p>先操作时间轴，再查看真实消息。完整规则、字段字典和Python源码图都在这一页，按目录逐项阅读。</p><div class="actions"><a href="#slot-widget">操作跨slot时间轴 ↓</a><a href="#messages-widget">查看实测消息 ↓</a><button id="download-rules">下载规则正文</button></div></header><noscript><p>交互控件需要JavaScript；完整正文、表格与UML仍可阅读。</p></noscript>${body[0]}<div class="subhero"><h2>Python源码理解</h2><p>对象关系、决策流程、后端状态与本地AST导航。</p></div>${body[1]}<footer>正文来自两份Markdown，SVG来自同名Mermaid。控件使用公开配置与构造条件，实测消息来自专项验证；本页不启动模型或比赛模拟器。<p><a href="v4-rules-and-protocol.md">规则权威</a> · <a href="python-source-map.md">源码地图</a> · <a href="#top">回到顶部 ↑</a></p></footer></main><script id="rules-data" type="application/json">${JSON.stringify(data).replace(/</g,'\\u003c')}</script><script>${js}</script></body></html>`;
fs.writeFileSync(path.join(root,'docs/survey-rules-explorer.html'),html);
fs.writeFileSync(path.join(root,'docs/survey-rules-explorer.build.json'),JSON.stringify({upstream_commit:settings.upstream_commit,sources:sources.map(s=>({path:'docs/'+s.name,sha256:digest(s.markdown)})),diagrams,assets:['page.css','page.js'].map(name=>({path:'scripts/rules_explorer/'+name,sha256:digest(fs.readFileSync(path.join(root,'scripts/rules_explorer',name)))})),output_sha256:digest(html),message_evidence:'experiments/current/rules-audit/evidence-refresh'},null,2)+'\n');
console.log('Built v4 rule and Python explorer: '+headings.length+' sections, '+diagrams.length+' diagrams.');
