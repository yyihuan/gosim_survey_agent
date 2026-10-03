#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""由 Root guide/报告、两套结果记录和既有流程 SVG 构建离线研究页。

不导入模拟器，不读取卡片、truth、原始轨迹，不修改冻结源码。
分数来自各自的机器记录；策略解释来自 Root guide/报告。
"""
import hashlib
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "scripts/strategy_study"
REPORT = ROOT / "docs/v4-strategy-study-report.md"
DATA = ROOT / "experiments/v4/results/all_runs.json"
FLOW = ROOT / "docs/diagrams/v4-strategy-experiment.svg"
OUTPUT = ROOT / "docs/v4-strategy-study.html"
GUIDE = ROOT / "docs/v4-strategy-study-guide.json"
EXTERNAL = ROOT / "experiments/v4/external_evaluation/results.json"
SCREENSHOTS = ROOT / "experiments/v4/external_evaluation/leaderboard-screenshots.json"
EXTENSION_DATA = ROOT / "experiments/v4/extension/results/all_runs.json"
EXTENSION_GUIDE = ROOT / "docs/v4-strategy-extension-guide.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inline_markdown(text):
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def report_paragraphs(report):
    paragraphs = [p.replace("\n", " ") for p in report.split("\n\n")]

    def paragraph(prefix):
        matches = [p for p in paragraphs if p.startswith(prefix)]
        if len(matches) != 1:
            # Root 同时编辑正文；缺省段落不阻止数据总览构建。
            return ""
        return "<p>" + inline_markdown(matches[0]) + "</p>"

    prefixes = {
        "lead": "本轮最重要的结果是：",
        "online": "官方练习卡下载和榜单接口",
        "generated": "本轮改用官方未修改的生成器",
        "limits": "独立保留集降低了",
        "stress": "日期参数的结束日",
        "T": "**T的机制确实触发了。**",
        "D": "**D在两卡都改善",
        "G": "**G提高了实际命中高度。**",
        "C": "**C没有实现本轮覆盖假设。**",
        "P": "**P说明局部搜索和整季结果不同。**",
        "W": "**W的结果否定本轮使用方式。**",
        "T_iteration": "**T的第二次调整最有解释价值。**",
        "D_iteration": "**D的指数不呈单调关系。**",
        "P_iteration": "**P的搜索收益也不单调。**",
        "selection": "**开封前的选择是DTGP。**",
        "interaction": "可用交互量描述非加性：",
        "transfer": "**开发冠军没有保持优势。**",
        "T_transfer": "**T的上下文效应发生反转。**",
        "CW_transfer": "**C/W的组合结论也反转了。**",
        "gap": "**绝对任务缺口仍大。**",
        "invalid": "stress的baseline有12条",
        "judgment1": "**第一，最强的证据指向",
        "judgment2": "**第二，收益代理需要",
        "judgment3": "**第三，局部偏好会",
        "judgment4": "**第四，防过拟合需要",
        "next1": "1. **为required建立",
        "next2": "2. **记录漏源原因。**",
        "next3": "3. **把覆盖和天气写成",
        "next4": "4. **取得新外部数据",
    }
    # Markdown 编号列表在同一块中；拆成独立段落再提取。
    paragraphs = [line for p in paragraphs for line in re.split(r" (?=[1-4]\. \*\*)", p)]
    return {key: paragraph(prefix) for key, prefix in prefixes.items()}


def optional_json(path):
    """外部评估可尚未写完；不把缺失/下载失败解读为零分。"""
    state = {"path": str(path.relative_to(ROOT)), "status": "missing", "sha256": None}
    if not path.exists():
        return None, state
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        state.update(status="unavailable", error=type(exc).__name__)
        return None, state
    state.update(status="loaded", sha256=digest(path))
    return value, state


def main():
    original = json.loads(DATA.read_text(encoding="utf-8"))
    rows = original["rows"]
    if original["row_count"] != len(rows):
        raise ValueError("all_runs 行数声明与实际不一致")
    r5 = [r for r in rows if r["stage_group"] == "R5"]
    if len(r5) != 26 or any(not r["full_season_complete"] for r in r5):
        raise ValueError("R5 必须是 26 条完整记录")
    report = REPORT.read_text(encoding="utf-8")
    guide, guide_state = optional_json(GUIDE)
    external, external_state = optional_json(EXTERNAL)
    screenshots, screenshot_state = optional_json(SCREENSHOTS)
    extension, extension_state = optional_json(EXTENSION_DATA)
    extension_guide, extension_guide_state = optional_json(EXTENSION_GUIDE)
    if extension and extension.get("row_count") != len(extension.get("rows", [])):
        raise ValueError("第二批 all_runs 行数声明与实际不一致")
    payload = {
        "data": original,
        "narrative": report_paragraphs(report),
        "guide": guide,
        "external_results": external,
        "leaderboard_screenshots": screenshots,
        "extension_data": extension,
        "extension_guide": extension_guide,
        "input_states": {"guide": guide_state, "external": external_state,
                         "screenshots": screenshot_state, "extension": extension_state,
                         "extension_guide": extension_guide_state},
        "external_source_links": [
            {"label": label, "path": str(path.relative_to(ROOT))}
            for label, path in [
                ("正式卡对照 CSV", EXTERNAL.with_suffix(".csv")),
                ("截图转录 CSV", SCREENSHOTS.with_suffix(".csv")),
                ("截图统计说明", SCREENSHOTS.parent / "screenshot-method.md"),
                ("公开环境获取证据", SCREENSHOTS.parent / "availability_diagnosis.json"),
            ] if path.exists()
        ],
        "build": {"report_sha256": digest(REPORT), "data_sha256": digest(DATA),
                  "flow_sha256": digest(FLOW), "builder_sha256": digest(Path(__file__)),
                  "template_sha256": digest(ASSETS / "page.html"),
                  "javascript_sha256": digest(ASSETS / "page.js"),
                  "stylesheet_sha256": digest(ASSETS / "page.css"),
                  "extension_javascript_sha256": digest(ASSETS / "extension.js"),
                  "extension_stylesheet_sha256": digest(ASSETS / "extension.css"),
                  "extension_data_sha256": extension_state["sha256"],
                  "extension_guide_sha256": extension_guide_state["sha256"],
                  "guide_sha256": guide_state["sha256"],
                  "external_results_sha256": external_state["sha256"],
                  "leaderboard_screenshots_sha256": screenshot_state["sha256"]},
    }
    # 保留原数据结构；只在浏览器中转换证据路径，下载仍是权威 JSON。
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    encoded = encoded.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    page = (ASSETS / "page.html").read_text(encoding="utf-8")
    replacements = {
        "__CSS__": (ASSETS / "page.css").read_text(encoding="utf-8") + "\n" + (ASSETS / "extension.css").read_text(encoding="utf-8"),
        "__JS__": (ASSETS / "page.js").read_text(encoding="utf-8") + "\n" + (ASSETS / "extension.js").read_text(encoding="utf-8"),
        "__PAYLOAD__": encoded,
        "__FLOW__": FLOW.read_text(encoding="utf-8"),
    }
    for key, value in replacements.items():
        if page.count(key) != 1:
            raise ValueError("模板占位符须唯一：" + key)
        page = page.replace(key, value)
    if re.search(r'<(?:script|link|img)[^>]+(?:src|href)="https?://', page):
        raise ValueError("离线页不得载入网络依赖")
    OUTPUT.write_text(page, encoding="utf-8")
    check = {"row_count": len(rows), "r5_rows": len(r5),
             "extension_rows": len(extension.get("rows", [])) if extension else 0,
             "extension_reference_rows": len(extension.get("reference_rows", [])) if extension else 0,
             "record_issues": sum(bool(r["record_issues"]) for r in rows),
             "output": str(OUTPUT.relative_to(ROOT)), "html_sha256": digest(OUTPUT),
             "inputs": payload["build"], "input_states": payload["input_states"],
             "generated_at_utc": original["generated_at_utc"]}
    (ROOT / "docs/v4-strategy-study.build.json").write_text(
        json.dumps(check, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(check, ensure_ascii=False))


if __name__ == "__main__":
    main()
