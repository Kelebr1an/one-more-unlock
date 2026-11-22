"""Update the configured Steam games and publish their progress index and journal."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from fetch_achievements import (
    APP_ID,
    PROFILE,
    FeedError,
    SteamClient,
    atomic_write,
    collect_snapshot,
    load_snapshot,
    resolve_steam_id,
    serialize_public,
    validate_replacement,
)


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_URL = "https://raw.githubusercontent.com/Kelebr1an/ror2-achievements-feed/main/data/"
PARTIAL_SUCCESS = 3


def snapshot_name(appid):
    # Preserve the link used by existing RoR2 chats and consumers.
    return "achievements.json" if appid == APP_ID else f"{appid}.json"


def journal_entry(slug, snapshot, previous):
    newly_unlocked = []
    if previous is not None:
        already_unlocked = {item["apiname"] for item in previous["achievements"] if item["achieved"]}
        newly_unlocked = [
            {key: item[key] for key in ("apiname", "name", "unlocktime")}
            for item in snapshot["achievements"]
            if item["achieved"] and item["apiname"] not in already_unlocked
        ]
        newly_unlocked.sort(key=lambda item: item["unlocktime"], reverse=True)
        if not newly_unlocked and all(snapshot[key] == previous[key] for key in ("total", "unlocked")):
            return None

    return {
        "game": slug,
        "fetched_at": snapshot["fetched_at"],
        "previous_fetched_at": previous["fetched_at"] if previous is not None else None,
        "total": snapshot["total"],
        "unlocked": snapshot["unlocked"],
        "remaining": snapshot["remaining"],
        "newly_unlocked": newly_unlocked,
    }


def build_index(games, snapshots, entries):
    latest = {entry["game"]: entry for entry in entries}
    summaries = {}
    for slug, game in games.items():
        snapshot = snapshots[slug]
        summary = {**game, "status": "not_fetched"}
        if snapshot is not None:
            complete = snapshot["remaining"] == 0
            timestamps = [item["unlocktime"] for item in snapshot["achievements"]]
            completed_at = (
                datetime.fromtimestamp(max(timestamps), timezone.utc).isoformat().replace("+00:00", "Z")
                if complete and all(timestamps) else None
            )
            summary.update({key: snapshot[key] for key in ("fetched_at", "total", "unlocked", "remaining")})
            summary.update(
                status="completed" if complete else "in_progress",
                achievements_url=DATA_URL + snapshot_name(game["appid"]),
                completed_at=completed_at,
                last_progress=latest.get(slug),
            )
        summaries[slug] = summary
    return {"profile": PROFILE, "journal_url": DATA_URL + "journal.json", "games": summaries}


def update_games(games, data_dir, selected, api_key="", *, client=None):
    paths = {slug: data_dir / snapshot_name(game["appid"]) for slug, game in games.items()}
    snapshots = {slug: load_snapshot(path, games[slug]["appid"]) for slug, path in paths.items()}
    journal_path = data_dir / "journal.json"
    entries = json.loads(journal_path.read_text(encoding="utf-8"))["entries"] if journal_path.exists() else []
    updates = {}
    failed = 0
    if selected:
        client = client if client is not None else SteamClient(api_key)
        steam_id = resolve_steam_id(client)
        for slug in selected:
            previous = snapshots[slug]
            try:
                snapshot = collect_snapshot(client, games[slug]["appid"], steam_id=steam_id)
                validate_replacement(previous, snapshot)
                content = serialize_public(snapshot, api_key)
            except FeedError as error:
                print(f"{slug}: {error}", file=sys.stderr)
                failed += 1
                continue
            entry = journal_entry(slug, snapshot, previous)
            if entry is not None:
                entries.append(entry)
            updates[paths[slug]] = content
            snapshots[slug] = snapshot
            print(f"{slug}: {snapshot['unlocked']}/{snapshot['total']} unlocked.")
        if not updates:
            return 1

    updates[journal_path] = serialize_public({"entries": entries}, api_key)
    updates[data_dir / "index.json"] = serialize_public(build_index(games, snapshots, entries), api_key)
    for path, content in updates.items():
        atomic_write(path, content)
    return PARTIAL_SUCCESS if failed else 0


def main(argv=None):
    games = json.loads((ROOT / "games.json").read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--game", choices=["all", *games])
    mode.add_argument("--rebuild-index", action="store_true", help="Build the index from existing snapshots only.")
    args = parser.parse_args(argv)
    selected = [] if args.rebuild_index else list(games) if args.game == "all" else [args.game]
    api_key = os.environ.get("STEAM_API_KEY", "") if selected else ""
    try:
        return update_games(games, DATA_DIR, selected, api_key)
    except FeedError as error:
        print(f"Update failed: {error}", file=sys.stderr)
    except Exception:
        print("Update failed unexpectedly; no diagnostic secrets were printed.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
