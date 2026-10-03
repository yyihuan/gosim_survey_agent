#!/usr/bin/env python3
"""单命令运行隔离的 v4 实验；输出目录存在时拒绝覆盖。"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from common import (EXPERIMENT_ROOT, HARNESS_ROOT, KIT_ROOT, SimulatorLease, copy_snapshot,
                    file_sha256, tree_manifest, write_json)
from metrics import extract

ENTRY_CANDIDATES = ("baseline_agent.py", "agent.py", "main.py")
ENV_KEY = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
PROTECTED_ENV = {"PATH", "HOME", "TMPDIR", "PYTHONPATH", "PYTHONSTARTUP", "LD_PRELOAD"}


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def terminate_signal(_signum, _frame):
    raise KeyboardInterrupt


def select_entry(agent: Path, entry: str | None) -> tuple[Path, Path]:
    if agent.is_file():
        if entry:
            raise ValueError("--agent 已指定文件时不接受 --entry")
        return agent.parent, Path(agent.name)
    if not agent.is_dir():
        raise ValueError(f"Agent 不存在：{agent}")
    candidates = [entry] if entry else ENTRY_CANDIDATES
    for candidate in candidates:
        selected = (agent / candidate).resolve()
        if selected.is_file() and agent in selected.parents:
            return agent, selected.relative_to(agent)
    raise ValueError(f"Agent 没有入口：{agent}；使用 --entry 指定相对路径")


def validate_environment(environment: dict) -> dict[str, str]:
    if not isinstance(environment, dict):
        raise ValueError("config.environment 必须是对象")
    validated = {}
    for key, value in environment.items():
        if (not ENV_KEY.fullmatch(key) or key in PROTECTED_ENV or key.startswith("OPENAI_")
                or any(marker in key for marker in ("API_KEY", "SECRET", "TOKEN"))):
            raise ValueError(f"本地实验不接受环境字段：{key}")
        if not isinstance(value, str):
            raise ValueError(f"环境值必须是字符串：{key}")
        if key == "USE_LLM" and value != "0":
            raise ValueError("本轮实验 USE_LLM 必须为 0")
        validated[key] = value
    validated["USE_LLM"] = "0"
    validated["PYTHONDONTWRITEBYTECODE"] = "1"
    return validated


def stop_owned_processes(process: subprocess.Popen, output: Path, proxy_entry: Path) -> None:
    # 官方 AgentProcess 建立了自己的 session；只能终止记录为本次 proxy 的进程组。
    pid_path = output / "proxy_pid.json"
    if pid_path.is_file():
        pid = json.loads(pid_path.read_text()).get("proxy_pid")
        if isinstance(pid, int):
            check = subprocess.run(["ps", "-p", str(pid), "-o", "command="],
                                   capture_output=True, text=True, timeout=2)
            if str(proxy_entry) in check.stdout:
                try:
                    os.killpg(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=3)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="唯一目录名；只接受字母、数字、点、横线与下划线")
    parser.add_argument("--agent", required=True, type=Path, help="Agent 目录或入口 .py 文件")
    parser.add_argument("--entry", help="目录内的入口相对路径；省略时沿用官方入口选择")
    parser.add_argument("--card", type=Path, default=KIT_ROOT / "cards/demo")
    parser.add_argument("--config", type=Path, help="JSON配置；归档并复制为 Agent 的 experiment_config.json")
    parser.add_argument("--env", action="append", default=[], help="配置 Agent 环境 KEY=VALUE；可重复")
    parser.add_argument("--stage", default="unspecified")
    parser.add_argument("--python", default="/usr/bin/python3")
    parser.add_argument("--wallclock", type=float, default=900)
    parser.add_argument("--init-timeout", type=float, default=30)
    parser.add_argument("--grace", type=float, default=30)
    parser.add_argument("--process-timeout", type=float, help="外层真实时间上限；缺省为 wallclock+init+grace+60")
    parser.add_argument("--lock-timeout", type=float, default=1800)
    parser.add_argument("--exclusive", action="store_true", help="同时取得两个槽，用于可比性基线")
    args = parser.parse_args(argv)
    signal.signal(signal.SIGTERM, terminate_signal)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", args.run_id):
        parser.error("run-id 不符合目录名规范")
    if min(args.wallclock, args.init_timeout, args.grace, args.lock_timeout) <= 0:
        parser.error("时间上限必须为正")
    process_timeout = args.process_timeout or min(args.wallclock, 900) + args.init_timeout + args.grace + 60
    if process_timeout <= 0:
        parser.error("process-timeout 必须为正")
    source, entry_rel = select_entry(args.agent.resolve(), args.entry)
    card_source = args.card.resolve()
    if not (card_source / "config/v4_scenario.json").is_file():
        parser.error("卡片缺少 config/v4_scenario.json")
    config_bytes = args.config.read_bytes() if args.config else b"{}\n"
    config = json.loads(config_bytes)
    if not isinstance(config, dict):
        parser.error("配置必须是 JSON 对象")
    environment = dict(config.get("environment", {}))
    for item in args.env:
        if "=" not in item:
            parser.error("--env 格式为 KEY=VALUE")
        key, value = item.split("=", 1)
        environment[key] = value
    environment = validate_environment(environment)
    runtime = subprocess.check_output([args.python, "--version"], text=True).strip()
    version = re.search(r"Python (\d+)\.(\d+)\.(\d+)", runtime)
    if not version or tuple(map(int, version.groups())) < (3, 9, 0):
        parser.error("实际 Python 必须至少为3.9")
    snapshot_record = json.loads((EXPERIMENT_ROOT / "vendor/snapshot_manifest.json").read_text())
    kit_hash = tree_manifest(KIT_ROOT)["tree_sha256"]
    if kit_hash != snapshot_record["snapshot_tree_sha256"]:
        parser.error("固定 vendor 快照 hash 已变化")
    run = EXPERIMENT_ROOT / "runs" / args.run_id
    run.mkdir(parents=True, exist_ok=False)
    overall_start = time.monotonic()
    manifest = {"schema_version": "v4-experiment-run-v1", "run_id": args.run_id, "stage": args.stage,
                "status": "setup", "start_utc": utc_now(), "source": str(source),
                "source_entry": entry_rel.as_posix(), "card_source": str(card_source),
                "python_executable": str(Path(args.python).resolve()), "python_version": runtime,
                "platform": platform.platform(), "upstream_commit": snapshot_record["upstream_commit"],
                "snapshot_tree_sha256": kit_hash,
                "harness_tree_sha256": tree_manifest(HARNESS_ROOT)["tree_sha256"],
                "requested_wallclock_seconds": args.wallclock, "process_timeout_seconds": process_timeout,
                "llm_enabled": False, "network_calls_authorized": False,
                "config_source": str(args.config.resolve()) if args.config else None,
                "agent_environment": environment}
    write_json(run / "manifest.json", manifest)
    process = None
    started = None
    output = run / "output"
    output.mkdir()
    proxy_entry = run / "agent/_harness_proxy.py"
    result_code = 1
    try:
        source_snapshot = copy_snapshot(source, run / "source_snapshot")
        write_json(run / "source_manifest.json", source_snapshot)
        card_snapshot = copy_snapshot(card_source, run / "card_snapshot")
        write_json(run / "card_manifest.json", card_snapshot)
        copy_snapshot(run / "source_snapshot", run / "agent", readonly=False)
        agent_root = run / "agent"
        (run / "config.json").write_bytes(config_bytes)
        (run / "config.json").chmod(0o444)
        (agent_root / "experiment_config.json").write_bytes(config_bytes)
        environment["EXPERIMENT_CONFIG_PATH"] = os.path.relpath(agent_root / "experiment_config.json",
                                                               (agent_root / entry_rel).parent)
        project_path = agent_root / "observer.project.json"
        project = json.loads(project_path.read_text()) if project_path.exists() else {}
        project["environment"] = {**validate_environment(project.get("environment", {})), **environment}
        write_json(project_path, project)
        for reserved in ("_harness_proxy.py", "_harness_proxy_config.json"):
            if (agent_root / reserved).exists():
                raise ValueError(f"Agent 使用了 harness 保留文件名：{reserved}")
        shutil.copy2(HARNESS_ROOT / "protocol_proxy.py", proxy_entry)
        write_json(agent_root / "_harness_proxy_config.json",
                   {"entry": str(agent_root / entry_rel), "telemetry_path": str(output / "protocol_telemetry.jsonl")})
        (run / "work").mkdir()
        (run / "tmp").mkdir()
        command = [args.python, "-B", str(KIT_ROOT / "local_runner.py"), "--agent", str(proxy_entry),
                   "--card", str(run / "card_snapshot"), "--out", str(output), "--python", args.python,
                   "--wallclock", str(args.wallclock), "--init-timeout", str(args.init_timeout),
                   "--grace", str(args.grace), "--quiet"]
        manifest.update({"source_tree_sha256": source_snapshot["tree_sha256"],
                         "card_tree_sha256": card_snapshot["tree_sha256"],
                         "config_sha256": file_sha256(run / "config.json"),
                         "effective_agent_tree_sha256": tree_manifest(agent_root)["tree_sha256"],
                         "card_snapshot": str(run / "card_snapshot"), "command": command,
                         "command_shell": __import__("shlex").join(command), "cwd": str(run / "work"),
                         "agent_cwd": str((agent_root / entry_rel).parent), "status": "waiting_for_lock"})
        write_json(run / "manifest.json", manifest)
        with SimulatorLease(args.run_id, exclusive=args.exclusive, timeout=args.lock_timeout) as lease:
            manifest["concurrency"] = lease.conditions
            manifest["runner_start_utc"] = utc_now()
            manifest["status"] = "running"
            write_json(run / "manifest.json", manifest)
            started = time.monotonic()
            runner_env = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "TMPDIR": str(run / "tmp"),
                          "PYTHONDONTWRITEBYTECODE": "1", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
            with (run / "runner_stdout.json").open("w") as stdout, (run / "runner_stderr.log").open("w") as stderr:
                process = subprocess.Popen(command, cwd=run / "work", env=runner_env, stdout=stdout,
                                           stderr=stderr, start_new_session=True, pass_fds=lease.fds)
                manifest["runner_pid"] = process.pid
                write_json(run / "manifest.json", manifest)
                try:
                    exit_code = process.wait(timeout=process_timeout)
                    manifest.update({"exit_code": exit_code, "status": "completed" if exit_code == 0 else "runner_error"})
                    result_code = exit_code if exit_code >= 0 else 1
                except subprocess.TimeoutExpired:
                    stop_owned_processes(process, output, proxy_entry)
                    manifest.update({"status": "guard_timeout", "exit_code": process.returncode,
                                     "termination_reason": "harness_guard_timeout"})
                    result_code = 124
                except BaseException:
                    stop_owned_processes(process, output, proxy_entry)
                    raise
            manifest["runtime_seconds"] = time.monotonic() - started
    except KeyboardInterrupt:
        manifest.update({"status": "interrupted", "termination_reason": "harness_interrupted"})
        result_code = 130
    except Exception as error:
        manifest.update({"status": "harness_error", "termination_reason": "harness_error",
                         "failure_detail": f"{type(error).__name__}: {error}"})
        print(manifest["failure_detail"], file=sys.stderr)
    finally:
        if process is not None and process.poll() is None:
            stop_owned_processes(process, output, proxy_entry)
        if process is not None:
            manifest.setdefault("exit_code", process.returncode)
        if started is not None:
            manifest.setdefault("runtime_seconds", time.monotonic() - started)
        manifest["end_utc"] = utc_now()
        manifest["runtime_with_setup_seconds"] = time.monotonic() - overall_start
        workflow_path = output / "workflow_result.json"
        if workflow_path.is_file():
            workflow = json.loads(workflow_path.read_text())
            manifest.setdefault("termination_reason", workflow["termination_reason"])
            manifest["official_termination_reason"] = workflow["termination_reason"]
        write_json(run / "manifest.json", manifest)
        metrics = extract(run)
        write_json(run / "metrics.json", metrics)
        print(json.dumps({"run_id": args.run_id, "status": manifest["status"], "total": metrics["total"],
                          "termination_reason": manifest.get("termination_reason"),
                          "runtime_seconds": manifest.get("runtime_seconds"), "metrics": str(run / "metrics.json")},
                         ensure_ascii=False, sort_keys=True))
    return result_code


if __name__ == "__main__":
    raise SystemExit(main())
