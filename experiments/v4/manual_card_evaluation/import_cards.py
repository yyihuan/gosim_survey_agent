#!/usr/bin/env python3
"""安全导入用户四个ZIP，保留字节散列；不解析truth。"""
import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
V4 = ROOT.parent
WORKSPACE = V4.parents[1]
sys.path.insert(0, str(V4 / "harness"))
from common import file_sha256, tree_manifest


def main():
    cards = []
    for card in ("alpha", "beta", "gamma", "delta"):
        archive = WORKSPACE / ("taskcard-" + card + ".zip")
        before = file_sha256(archive)
        members = []
        seen = set()
        with zipfile.ZipFile(archive) as handle:
            infos = handle.infolist()
            assert sum(info.file_size for info in infos) <= 50 * 1024 * 1024
            for info in infos:
                name = info.filename
                path = PurePosixPath(name)
                assert not path.is_absolute() and "\\" not in name and "\0" not in name and ".." not in path.parts
                if path.parts[:2] == ("cards", card):
                    relative_parts = path.parts[2:]
                else:
                    assert path.parts[:1] == (card,), "非本卡路径：" + name
                    relative_parts = path.parts[1:]
                assert name not in seen, "ZIP重复路径：" + name
                seen.add(name)
                assert stat.S_IFMT(info.external_attr >> 16) != stat.S_IFLNK, "不接受符号链接"
                if info.is_dir():
                    continue
                rel = Path(*relative_parts)
                assert rel.parts[0] in ("config", "public", "truth")
                assert info.file_size <= 10 * 1024 * 1024
                raw = handle.read(info)  # zipfile同时校验CRC；truth仅复制与散列。
                digest = hashlib.sha256(raw).hexdigest()
                target = ROOT / "cards" / card / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as output:
                    output.write(raw)
                previous = V4 / "external_evaluation/cards" / card / rel
                members.append({"zip_member": name, "relative_path": rel.as_posix(), "bytes": len(raw),
                                "sha256": digest, "crc32": f"{info.CRC:08x}",
                                "previous_download_exists": previous.is_file(),
                                "equal_previous_download": previous.is_file() and file_sha256(previous) == digest})
        assert before == file_sha256(archive), "导入期间ZIP改变"
        base = ROOT / "cards" / card
        scenario = json.loads((base / "config/v4_scenario.json").read_text())
        inputs = [scenario["fiber_config"], scenario["score_config"], *scenario["products"].values()]
        if scenario.get("stress", {}).get("enabled"):
            inputs.append(scenario["stress"]["stress_events_csv"])
        missing = []
        for name in inputs:
            product = (base / "config" / name).resolve()
            assert base.resolve() in product.parents
            if not product.is_file():
                missing.append(product.relative_to(base.resolve()).as_posix())
        files = {member["relative_path"]: member["sha256"] for member in members}
        facts_path = WORKSPACE / "research/2026-10-02/upstream/cards" / ("v4-practice-" + card) / "card.json"
        facts = json.loads(facts_path.read_text())
        cards.append({"card_id": card, "archive": str(archive.relative_to(WORKSPACE)), "archive_sha256": before,
                      "archive_bytes": archive.stat().st_size, "file_count": len(members), "members": members,
                      "all_files_equal_previous_download": all(member["equal_previous_download"] for member in members),
                      "same_file_set_as_previous": set(files) == {path.relative_to(V4 / "external_evaluation/cards" / card).as_posix()
                                                                for path in (V4 / "external_evaluation/cards" / card).rglob("*") if path.is_file()},
                      "local_path": "cards/" + card, "tree_sha256": tree_manifest(base)["tree_sha256"],
                      "bundle_manifest_sha256_partial": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
                      "official_bundle_checksum": facts["checksum"], "official_facts": facts,
                      "runner_required_missing": sorted(set(missing)), "legal_complete_local_bundle": not missing})
        for path in base.rglob("*"):
            path.chmod(0o555 if path.is_dir() else 0o444)
        base.chmod(0o555)
    inventory = {"schema_version": "v4-manual-card-import-v1", "imported_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 "script_sha256": file_sha256(Path(__file__)), "cards": cards,
                 "truth_policy": "copy and hashes only; no truth content analysis",
                 "safe_extract_checks": ["card-specific relative path", "no traversal", "no symlink", "no duplicate", "bounded size", "CRC verified", "never overwrite"],
                 "all_four_legal_complete_local_bundles": all(card["legal_complete_local_bundle"] for card in cards)}
    with (ROOT / "card_inventory.json").open("x") as output:
        json.dump(inventory, output, ensure_ascii=False, indent=2, sort_keys=True)
        output.write("\n")
    print(json.dumps([{key: card[key] for key in ("card_id", "file_count", "all_files_equal_previous_download", "runner_required_missing")}
                      for card in cards], ensure_ascii=False))


if __name__ == "__main__":
    main()
