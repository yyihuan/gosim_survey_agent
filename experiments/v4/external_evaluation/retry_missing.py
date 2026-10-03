#!/usr/bin/env python3
"""对首次清单所缺官方对象有界定点请求；保留首次清单与失败记录。"""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import time
import collect_cards as collector


def fetch(item):
    card, key = item
    name = "missing-" + card + "-" + key.replace("/", "-")
    try:
        raw, evidence = collector.request(name, "/storage/v1/object/scenarios/v4-practice-" + card + "/" + key)
        target = collector.ROOT / "cards" / card / key
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            handle.write(raw)
        value = {"card_id": card, "relative_path": key, "local_path": str(target.relative_to(collector.ROOT)),
                 "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "source_url": evidence["url"],
                 "retrieved_at_utc": evidence["finished_at_utc"], "evidence_path": evidence["evidence_path"]}
        print(json.dumps({"card": card, "path": key, "downloaded": True}), flush=True)
        return value, None
    except Exception as exc:
        failure = {"card": card, "relative_path": key, "error": type(exc).__name__ + ": " + str(exc)}
        print(json.dumps(failure), flush=True)
        return None, failure


def main():
    original = json.loads((collector.ROOT / "card_inventory.json").read_text())
    todo = [(card["card_id"], key) for card in original["cards"] for key in card["missing_required"]]
    collector.write_new(collector.ROOT / "acquisition/missing01-operation.json", {
        "started_at_utc": collector.now(), "source_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "authorization": "Root: diagnose missing objects; bounded targeted retries; verified cards may run separately",
        "targets": [{"card": card, "relative_path": key} for card, key in todo],
        "maximum_parallel": 2, "maximum_attempts_each": 2, "timeout_seconds_each": collector.TIMEOUT,
        "whole_phase_deadline_seconds": collector.DEADLINE_SECONDS,
        "first_inventory_preserved": "card_inventory.json", "truth_policy": "download and hashes only"})
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(fetch, todo))
    files = [item for card in original["cards"] for item in card["files"]]
    files += [value for value, failure in outcomes if value]
    failures = [failure for value, failure in outcomes if failure]
    cards = [collector.metadata(card, [item for item in files if item["card_id"] == card]) for card in collector.CARDS]
    updated = {**original, "created_at_utc": collector.now(), "cards": cards,
               "all_four_verified": all(card["verified"] for card in cards),
               "distinct_cards_by_manifest": len({card["bundle_manifest_sha256"] for card in cards}),
               "first_inventory": "card_inventory.json", "missing_object_probe_failures": failures,
               "targeted_download_count": len(todo), "targeted_download_successes": sum(bool(value) for value, failure in outcomes),
               "targeted_phase_runtime_seconds": time.monotonic() - collector.STARTED}
    collector.write_new(collector.ROOT / "card_inventory_complete.json", updated)
    for card in cards:
        if card["verified"]:
            base = collector.ROOT / card["local_path"]
            for path in base.rglob("*"):
                path.chmod(0o555 if path.is_dir() else 0o444)
            base.chmod(0o555)
    print(json.dumps({"verified_cards": [card["card_id"] for card in cards if card["verified"]],
                      "missing_object_count": len(todo), "successful_downloads": updated["targeted_download_successes"]}), flush=True)
    return 0 if updated["all_four_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
