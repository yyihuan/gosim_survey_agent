#!/usr/bin/env node
// 正文和表格以 Markdown 为权威；生成页不作为编辑入口。
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const doc = path.join(root, 'docs/v4-llm-collaboration.md');
const assets = path.join(root, 'scripts/llm_collaboration');
let marked;
try {
  ({ marked } = await import('marked'));
} catch {
  const modules = process.env.SURVEY_DOC_MODULES || '/Users/cxjh168/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
  ({ marked } = await import(pathToFileURL(path.join(modules, 'marked/lib/marked.esm.js')).href));
}

const md = fs.readFileSync(doc, 'utf8');
const escape = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const digest = text => createHash('sha256').update(text).digest('hex');
function table(name) {
  const hit = md.match(new RegExp(`<!-- data:${name} -->\\s*([\\s\\S]*?)(?=\\n\\n)`));
  if (!hit) throw new Error(`Missing authoritative table: ${name}`);
  const rows = hit[1].trim().split('\n').map(l => l.split('|').slice(1, -1).map(c => c.trim()));
  return { columns: rows[0], rows: rows.slice(2) };
}

const settings = JSON.parse(fs.readFileSync(path.join(root, 'experiments/current/environment.json'), 'utf8'));
const config = JSON.parse(fs.readFileSync(path.join(root, settings.cards, 'L1/config/v4_score_config.json'), 'utf8'));
const data = {
  markdown: md,
  steps: table('steps').rows,
  scenarios: table('scenarios').rows,
  evidence: table('evidence').rows.map(([name, dev, holdout, meaning]) => ({name, dev: Number(dev), holdout: Number(holdout), meaning})),
  reference: {
    f0t0: config.flux_zero_point * config.exposure_zero_point_seconds,
    threshold: config.required.observed_factor_threshold,
    penalty: config.required.penalty_per_missing,
    minimumAltitude: 30, maximumExposure: 3600, wallclock: 900
  }
};

const widgets = {
  evidence: `<div class="interactive" id="evidence-widget"><div class="widget-heading"><span class="chip fact">已有实验</span><h3>同一策略，从开发集走到保留集</h3></div><p class="helper">默认同时展示六根柱。柱越长，表示相对同卡基线的平均增量越大；它不代表 LLM 的收益。</p><div id="evidence-chart" class="evidence-chart" role="img" aria-label="D、DTGP、DPG在开发与保留研究卡上的平均分数增量"></div><div class="legend"><span><i class="swatch dev"></i>开发两卡</span><span><i class="swatch holdout"></i>保留两卡</span></div></div>`,
  flow: `<div class="interactive" id="flow-widget"><div class="widget-heading"><span class="chip demo">流程演示</span><h3>跟着一轮决策走一遍</h3></div><p class="helper">选择情景，再点击步骤。这里演示建议接入位置，按钮不会启动模型或比赛模拟器。</p><div class="flow-controls"><label>当前情景<select id="scenario-select" aria-label="当前情景"></select></label><label class="switch"><input id="llm-enabled" type="checkbox" checked>允许按事件接入 LLM</label><button id="flow-reset" class="quiet">回到第一步</button></div><p id="scenario-evidence" class="scenario-evidence"></p><div class="stepper" id="decision-stepper" aria-label="八步决策流程"></div><div class="flow-readout" id="flow-readout" aria-live="polite"></div><div class="step-footer"><span id="step-position"></span><div><button id="step-prev" class="quiet">上一步</button><button id="step-next">下一步</button></div></div><p class="helper">青绿色是程序；金色是模型接入。即使接入模型，第 6 步仍由程序检查建议，第 7 步仍由程序提交动作。</p></div>`,
  exposure: `<div class="interactive" id="exposure-widget"><div class="widget-heading"><span class="chip demo">构造计算</span><h3>曝光深度：两次短曝，能合成一次深曝吗？</h3></div><p class="helper">流量和 Q 是你设定的恒定条件。高度滑块表示全程最低高度；实际条件会随时间变化。</p><div class="controls-grid"><label>目标流量 f <output id="flux-value"></output><input id="flux" type="range" min="0.05" max="1" step="0.05" value="0.2"></label><label>假设质量 Q <output id="quality-value"></output><input id="quality" type="range" min="0.1" max="1.5" step="0.05" value="1"></label><label>每次曝光 T / 秒 <output id="duration-value"></output><input id="duration" type="range" min="60" max="3600" step="15" value="450"></label><label>全程最低高度 / 度 <output id="altitude-value"></output><input id="altitude" type="range" min="15" max="90" step="1" value="60"></label></div><div class="factor-chart" role="img" aria-label="单次与重复曝光的完成因子"><div><span>一次曝光</span><div class="factor-track"><i id="factor-once"></i><b class="threshold-line"></b></div><strong id="factor-once-value"></strong></div><div><span>两次相同曝光<br><small>只取最好一次</small></span><div class="factor-track"><i id="factor-twice"></i><b class="threshold-line"></b></div><strong id="factor-twice-value"></strong></div><div class="factor-axis"><span>g = 0</span><span>0.5 必做门槛</span><span>g = 1</span></div></div><div class="metric-grid"><div><span>估计最低达标时长</span><strong id="minimum-duration"></strong></div><div><span>参考时长内是否可达标</span><strong id="threshold-reachable"></strong></div><div><span>当前是否达标</span><strong id="threshold-status"></strong></div></div><p id="exposure-explanation" class="result-box" aria-live="polite"></p><button id="exposure-reset" class="quiet">恢复文中的例子</button></div>`,
  tradeoff: `<div class="interactive" id="tradeoff-widget"><div class="widget-heading"><span class="chip demo">构造计算</span><h3>科学分较低的计划，也可能更值得做</h3></div><p class="helper">假设 A 新增40科学分、B 新增25科学分；只有 B 完成下方这一组未完成必做源。此例省略覆盖、请求和其他机会成本。</p><div class="controls-grid"><label>B 可以完成的必做源数 <output id="saved-value"></output><input id="saved" type="range" min="0" max="5" step="1" value="1"></label><label class="switch"><input id="future-opportunity" type="checkbox">这组源之后仍有机会完成</label></div><div class="plan-cards"><div class="plan-card" id="plan-a"><span>计划 A · 当前科学收益高</span><strong id="plan-a-score">40</strong><p id="plan-a-math"></p></div><div class="plan-card" id="plan-b"><span>计划 B · 优先完成必做</span><strong id="plan-b-score">25</strong><p id="plan-b-math"></p></div></div><p id="tradeoff-explanation" class="result-box" aria-live="polite"></p><p class="helper">这是一个隔离两项影响的示例。“之后有窗口”不等于保证成功；实际后续完成概率需要估计。</p></div>`,
  budget: `<div class="interactive" id="budget-widget"><div class="widget-heading"><span class="chip demo">构造计算</span><h3>模型思考期间，真实预算还在消耗</h3></div><p class="helper">三个数都可改变。此处把处理时间顺序相加，不是实际模型或平台测速。</p><div class="controls-grid"><label>模型调用次数 <output id="calls-value"></output><input id="calls" type="range" min="0" max="200" step="1" value="12"></label><label>每次平均等待 / 秒 <output id="latency-value"></output><input id="latency" type="range" min="1" max="30" step="1" value="5"></label><label>程序与平台处理 / 秒 <output id="base-time-value"></output><input id="base-time" type="range" min="30" max="900" step="30" value="240"></label></div><div class="time-budget"><div class="budget-track" role="img" aria-label="真实时间预算分配"><span id="budget-base"></span><span id="budget-model"></span><span id="budget-left"></span></div><div class="legend"><span><i class="swatch holdout"></i>程序与平台</span><span><i class="swatch model"></i>模型等待</span><span><i class="swatch remaining"></i>剩余预算</span></div></div><div class="metric-grid"><div><span>模型等待合计</span><strong id="model-seconds"></strong></div><div><span>总耗时估计</span><strong id="total-seconds"></strong></div><div><span>距900秒上限</span><strong id="left-seconds"></strong></div></div><p id="budget-explanation" class="result-box" aria-live="polite"></p></div>`
};

let rendered = marked.parse(md, { gfm: true });
rendered = rendered.replace(/<!-- data:[a-z]+ -->\s*/g, '');
rendered = rendered.replace(/<!-- interactive:([a-z]+) -->/g, (_, name) => {
  if (!widgets[name]) throw new Error(`Unknown widget: ${name}`);
  return widgets[name];
});
rendered = rendered.replace(/<p><img src="(\.\/diagrams\/[^" ]+\.svg)" alt="([^"]*)"\s*\/?><\/p>/g, (_, relative, alt) => {
  const svgPath = path.resolve(path.dirname(doc), relative);
  const source = fs.readFileSync(svgPath.replace(/\.svg$/, '.mmd'), 'utf8');
  const svg = fs.readFileSync(svgPath, 'utf8');
  if (!svg.includes(`data-document-diagrams-source-sha256="${digest(source)}"`)) throw new Error(`Stale diagram: ${relative}`);
  // 配对 SVG 保持 Skill 原始生成结果；嵌入 HTML 时只移除外部字体请求。
  const offlineSvg = svg.replace(/@import\s+url\([^)]*\)\s*;/g, '');
  return `<details class="diagram-panel"><summary>查看完整流程图：${alt}</summary><figure aria-label="${alt}">${offlineSvg}<figcaption>${alt}。图源与 Markdown 文档共用。</figcaption></figure></details>`;
});
rendered = rendered.replace(/<table>([\s\S]*?)<\/table>/g, '<div class="table-scroll" tabindex="0"><table>$1</table></div>');

const title = md.match(/^# (.+)$/m)[1];
rendered = rendered.replace(/^<h1>[\s\S]*?<\/h1>\s*/, '');
const pieces = rendered.split(/(?=<h2>)/);
const intro = pieces.shift();
const headings = [];
const sections = pieces.map((part, i) => {
  const heading = part.match(/^<h2>([\s\S]*?)<\/h2>/)[1];
  const navText = heading.replace(/^\d+\.\s*/, '');
  const id = `part-${i + 1}`;
  headings.push({id, text: navText});
  return `<section class="doc-section" id="${id}" aria-labelledby="heading-${i+1}"><div class="section-number">${String(i+1).padStart(2,'0')}</div>${part.replace(/^<h2>/, `<h2 id="heading-${i+1}">`)}</section>`;
}).join('\n');
const css = fs.readFileSync(path.join(assets, 'page.css'), 'utf8');
const js = fs.readFileSync(path.join(assets, 'page.js'), 'utf8');
const json = JSON.stringify(data).replace(/</g, '\\u003c');
const html = `<!doctype html>
<html lang="zh-CN" data-source-sha256="${digest(md)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>${escape(title)}</title><style>${css}</style></head>
<body><a href="#main" class="skip-link">跳到正文</a><aside class="sidebar"><a href="#top" class="brand"><span class="brand-mark">◎</span><span>巡天 Agent<small>固定程序与 LLM 协作</small></span></a><p class="sidebar-note">先看决策怎样走，<br>再看模型在哪里接入。</p><nav aria-label="文档目录">${headings.map((h,i)=>`<a href="#${h.id}"><span>${String(i+1).padStart(2,'0')}</span>${h.text}</a>`).join('')}</nav><div class="sidebar-bottom">规则快照 · 2026.10.03<br>设计文档 · 2026.10.03<br><a href="v4-strategy-study.html">← 前一轮策略实验</a></div></aside>
<main id="main"><header id="top" class="hero"><div class="eyebrow">AGENT OBSERVER · v4</div><h1>程序算清每次曝光。<br><span>模型参与关键判断。</span></h1><p class="hero-description">从环境消息，到候选方案、模型建议与最终动作。用一轮完整决策，理解两者怎样共同工作。</p><div class="hero-actions"><a class="button" href="#flow-widget">逐步看一轮决策 <span>↓</span></a><button id="download-markdown" class="quiet">下载 Markdown</button></div><div class="role-legend"><span><i class="role-dot program"></i>程序：计算、检查、执行</span><span><i class="role-dot llm"></i>LLM：诊断、阶段规划</span><span><i class="role-dot environment"></i>环境：执行、反馈、计分</span></div></header>
<div class="intro">${intro}</div><noscript><p class="result-box">交互需要启用 JavaScript。全部文字、表格和完整流程图仍可阅读。</p></noscript>${sections}<footer><strong>同一份说明，两种阅读方式。</strong><p>正文和表格来自 Markdown，流程图来自同名 Mermaid 源。HTML 内嵌图表、样式和交互，可离线阅读。教学控件不会调用模型。</p><a href="#top">回到顶部 ↑</a></footer></main>
<script id="document-data" type="application/json">${json}</script><script>${js}</script></body></html>`;
const output = path.join(root, 'docs/v4-llm-collaboration.html');
fs.writeFileSync(output, html);
console.log(`Built ${path.relative(root, output)} (${Buffer.byteLength(html)} bytes); Markdown, ${data.steps.length} steps, ${data.scenarios.length} scenarios, ${data.evidence.length} experiment rows.`);
