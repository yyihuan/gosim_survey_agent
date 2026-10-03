#!/usr/bin/env python3
"""采集固定白名单中的官方公开四卡；不解析 truth，不修改旧采集证据。"""
import base64
import concurrent.futures
import csv
import datetime
import hashlib
import json
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
V4 = ROOT.parent
WORKSPACE = V4.parents[1]
UPSTREAM = WORKSPACE / "research/2026-10-02/upstream"
CARDS = ("alpha", "beta", "gamma", "delta")
TIMEOUT = 15
DEADLINE_SECONDS = 240
source_path = V4 / "data/public-source/supabase-HbgHf8cp.js"
source = source_path.read_text()
HOST = next(u for u in re.findall(r"https://[a-z0-9]+\.supabase\.co", source) if "placeholder" not in u)
KEY = re.findall(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", source)[0]
assert json.loads(base64.urlsafe_b64decode(KEY.split(".")[1] + "==="))["role"] == "anon"
STARTED = time.monotonic()
LOCK = threading.Lock()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def event(value):
    with LOCK, (ROOT / "acquisition/collect01/events.jsonl").open("a") as handle:
        handle.write(json.dumps({"at_utc": now(), **value}, ensure_ascii=False) + "\n")


def request(name, path, payload=None, *, retries=1, include_body=False):
    body = json.dumps(payload).encode() if payload is not None else None
    for index in range(retries + 1):
        remaining = DEADLINE_SECONDS - (time.monotonic() - STARTED)
        if remaining <= 0:
            raise TimeoutError("采集整体240秒期限已到，不再发新请求")
        req = urllib.request.Request(HOST + path, data=body,
                                     headers={"apikey": KEY, "Authorization": "Bearer " + KEY,
                                              "Content-Type": "application/json"})
        status = None; error = None; raw = b""; headers = {}
        began = time.monotonic(); started = now()
        try:
            with urllib.request.urlopen(req, timeout=min(TIMEOUT, remaining)) as response:
                status = response.status; raw = response.read(); headers = dict(response.headers)
        except urllib.error.HTTPError as exc:
            status = exc.code; raw = exc.read(); headers = dict(exc.headers)
        except Exception as exc:
            error = type(exc).__name__ + ": " + str(exc)
        evidence = {"name": name, "url": HOST + path, "method": "POST" if body else "GET",
                    "request_payload": payload, "attempt": index + 1, "http_status": status,
                    "started_at_utc": started, "finished_at_utc": now(),
                    "runtime_seconds": time.monotonic() - began, "error": error,
                    "response_headers": headers, "bytes": len(raw),
                    "body_sha256": hashlib.sha256(raw).hexdigest(), "permission": "public_frontend_anon"}
        if include_body or status != 200:
            evidence["body"] = raw.decode("utf-8", errors="replace")
        rel = "acquisition/collect01/" + name + "-attempt" + str(index + 1) + ".json"
        write_new(ROOT / rel, evidence)
        event({"event": "request", "name": name, "http_status": status, "error": error,
               "evidence": rel, "attempt": index + 1})
        if status == 200:
            return raw, {**evidence, "evidence_path": rel}
        if status is not None and status not in (429, 500, 502, 503, 504, 544):
            break
    raise RuntimeError(json.dumps({"name": name, "http_status": status, "error": error, "evidence": rel}))


def listing(pair):
    card, folder = pair
    old = ROOT / "acquisition/probe01" / (card + "-config-listing.json")
    if folder == "config" and old.exists():
        record = json.loads(old.read_text())
        if record["http_status"] == 200:
            return card, folder, json.loads(record["body"])
    # α/β config已在probe01失败过，补一次；其他目录至多两次。
    retries = 0 if folder == "config" and old.exists() else 1
    raw, _ = request(card + "-" + folder + "-listing", "/storage/v1/object/list/scenarios",
                     {"prefix": "v4-practice-" + card + "/" + folder,
                      "limit": 1000, "offset": 0, "sortBy": {"column": "name", "order": "asc"}},
                     retries=retries, include_body=True)
    return card, folder, json.loads(raw)


def download(item):
    card, key = item
    target = ROOT / "cards" / card / key
    cached = ROOT / "acquisition/probe01/alpha-known-config.json"
    if card == "alpha" and key == "config/v4_scenario.json" and target.exists():
        evidence = json.loads(cached.read_text()); raw = target.read_bytes()
        assert evidence["http_status"] == 200 and hashlib.sha256(raw).hexdigest() == evidence["body_sha256"]
        evidence_path = "acquisition/probe01/alpha-known-config.json"
    else:
        raw, evidence = request(card + "-" + key.replace("/", "-"),
                                "/storage/v1/object/scenarios/v4-practice-" + card + "/" + key)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            handle.write(raw)
        evidence_path = evidence["evidence_path"]
    return {"card_id": card, "relative_path": key, "local_path": str(target.relative_to(ROOT)),
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "source_url": evidence["url"], "retrieved_at_utc": evidence["finished_at_utc"],
            "evidence_path": evidence_path}


def metadata(card, files):
    # truth文件到此仅用于字节散列与文件完整性，不解析其内容。
    facts_path = UPSTREAM / "cards" / ("v4-practice-" + card) / "card.json"
    facts = json.loads(facts_path.read_text())
    expected = {"config/v4_scenario.json", "config/v4_fiber_config.json", "config/v4_score_config.json",
                "public/targets.csv", "public/footprint.csv", "public/v4_night_calendar.csv",
                "public/v4_bulletins.jsonl", "public/v4_forecasts.jsonl",
                "truth/v4_weather_truth.csv", "truth/v4_slots.csv", "truth/v4_events.csv",
                "truth/v4_earthquake_effects.csv", "truth/v4_observation_requests.jsonl"}
    if facts["stress"]:
        expected.add("truth/v4_stress_events.csv")
    manifest = {item["relative_path"]: item["sha256"] for item in files}
    checksum = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    complete = expected.issubset(manifest)
    match = checksum == facts["checksum"]
    base = ROOT / "cards" / card
    with (base / "public/targets.csv").open() as handle:
        targets = list(csv.DictReader(handle))
    with (base / "public/v4_night_calendar.csv").open() as handle:
        nights = list(csv.DictReader(handle))
    public_counts_match = (len(targets) == facts["targets"] and len(nights) == facts["nights"]
                           and sum(row["required"] == "true" for row in targets) == facts["required"])
    return {"card_id": card, "slug": "v4-practice-" + card, "local_path": "cards/" + card,
            "file_count": len(files), "bytes": sum(item["bytes"] for item in files),
            "bundle_manifest_sha256": checksum, "official_bundle_checksum": facts["checksum"],
            "checksum_matches_official": match, "required_files_complete": complete,
            "missing_required": sorted(expected - set(manifest)), "public_counts_match_official": public_counts_match,
            "verified": complete and match and public_counts_match,
            "official_facts": facts, "official_facts_path": str(facts_path.relative_to(WORKSPACE)),
            "official_facts_file_sha256": hashlib.sha256(facts_path.read_bytes()).hexdigest(),
            "files": sorted(files, key=lambda item: item["relative_path"])}


def main():
    evidence_dir = ROOT / "acquisition/collect01"
    evidence_dir.mkdir(parents=True, exist_ok=False)
    write_new(evidence_dir / "operation.json", {
        "started_at_utc": now(), "source_script": "collect_cards.py",
        "source_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "derived_from": "experiments/v4/data/collect_public.py", "permission": "public_frontend_anon",
        "host": HOST, "cards": list(CARDS), "maximum_request_concurrency": 2,
        "timeout_seconds_per_request": TIMEOUT, "whole_collection_deadline_seconds": DEADLINE_SECONDS,
        "maximum_attempts_per_endpoint_including_probe01": 2,
        "truth_policy": "download and hashes only; successful truth bodies not written to request logs",
        "key_source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest()})
    pairs = [(card, folder) for card in CARDS for folder in ("config", "public", "truth")]
    try:
        listings = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(listing, pair) for pair in pairs]
            for future in futures:
                listings.append(future.result())
        todo = []
        for card, folder, items in listings:
            if not isinstance(items, list) or len(items) >= 1000:
                raise ValueError("目录响应类型或截断风险：" + card + "/" + folder)
            for item in items:
                if not (item.get("id") or item.get("metadata")):
                    raise ValueError("出现嵌套目录，不默默跳过：" + card + "/" + folder)
                name = item["name"]
                if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or ".." in name:
                    raise ValueError("非安全对象路径")
                todo.append((card, folder + "/" + name))
        print("CHECKPOINT all listings available; files=" + str(len(todo)), flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            files = list(pool.map(download, todo))
        cards = [metadata(card, [item for item in files if item["card_id"] == card]) for card in CARDS]
        value = {"schema_version": "v4-external-card-inventory-v1", "created_at_utc": now(),
                 "source_page": "https://create.gosim.org/survey26/platform/resources",
                 "source_host": HOST, "api_discovered_from": "experiments/v4/data/public-source/supabase-HbgHf8cp.js",
                 "upstream_commit": "18be105bc517938c8341ad79646cf397e3293016",
                 "checksum_definition": "SHA256(json.dumps(relative_path to file SHA256 map, sort_keys=True).encode())",
                 "checksum_authority": "fixed official cards/card.json and scripts/build-v4-practice-cards.py::bundle_facts",
                 "truth_policy": "download and byte hashes only; no truth content analysis",
                 "cards": cards, "all_four_verified": all(card["verified"] for card in cards),
                 "distinct_cards_by_manifest": len({card["bundle_manifest_sha256"] for card in cards})}
        write_new(ROOT / "card_inventory.json", value)
        if not value["all_four_verified"]:
            raise ValueError("至少一张真实卡未通过官方checksum或完整性校验；不启动评估")
        for card in CARDS:
            for path in (ROOT / "cards" / card).rglob("*"):
                path.chmod(0o555 if path.is_dir() else 0o444)
            (ROOT / "cards" / card).chmod(0o555)
        print("CHECKPOINT four official cards verified; " + str([(card["card_id"], card["file_count"]) for card in cards]), flush=True)
        event({"event": "collection_completed", "all_four_verified": True})
        return 0
    except Exception as exc:
        write_new(ROOT / "collection_failure.json", {"at_utc": now(), "error": type(exc).__name__ + ": " + str(exc),
                  "status": "blocked_no_synthetic_replacement", "runtime_seconds": time.monotonic() - STARTED})
        event({"event": "collection_failed", "error": str(exc)})
        print("CHECKPOINT collection failed: " + str(exc), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
