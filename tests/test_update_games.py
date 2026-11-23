import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import update_games as tracker
from test_feed import KEY, STEAM_ID, achievement, payload


GAMES = json.loads((tracker.ROOT / "games.json").read_text(encoding="utf-8"))


def game_payload(slug, entries=None):
    response = payload(entries)
    response["playerstats"]["appid"] = GAMES[slug]["appid"]
    return response


class TrackerTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.data_dir = Path(directory.name)

    def read(self, filename):
        return json.loads((self.data_dir / filename).read_text(encoding="utf-8"))

    def update(self, selected, *responses):
        client = Mock()
        client.get.side_effect = [{"response": {"success": 1, "steamid": STEAM_ID}}, *responses]
        with patch("sys.stdout", io.StringIO()), patch("sys.stderr", io.StringIO()):
            status = tracker.update_games(GAMES, self.data_dir, selected, KEY, client=client)
        return status, client

    def test_shared_identity_and_independent_snapshots(self):
        status, client = self.update(list(GAMES), *(game_payload(slug) for slug in GAMES))
        self.assertEqual(status, 0)
        self.assertEqual(client.get.call_count, len(GAMES) + 1)
        self.assertEqual([call.args[1]["appid"] for call in client.get.call_args_list[1:]],
                         [game["appid"] for game in GAMES.values()])
        index = self.read("index.json")["games"]
        for slug, game in GAMES.items():
            appid = game["appid"]
            filename = "achievements.json" if slug == "ror2" else f"{appid}.json"
            with self.subTest(slug=slug):
                self.assertEqual(self.read(filename)["appid"], appid)
                self.assertTrue(index[slug]["achievements_url"].endswith("/" + filename))

    def test_journal_only_records_new_unlocks_after_baseline(self):
        self.update(["phantom-blade-zero"], game_payload("phantom-blade-zero"))
        self.assertEqual(self.read("journal.json")["entries"][0]["newly_unlocked"], [])
        complete = game_payload("phantom-blade-zero", [achievement(), achievement("two")])
        self.update(["phantom-blade-zero"], complete)
        self.update(["phantom-blade-zero"], complete)
        entries = self.read("journal.json")["entries"]
        self.assertEqual(len(entries), 2)
        self.assertEqual([item["apiname"] for item in entries[-1]["newly_unlocked"]], ["two"])
        index = self.read("index.json")["games"]
        self.assertEqual(index["phantom-blade-zero"]["status"], "completed")
        self.assertEqual(index["phantom-blade-zero"]["completed_at"], "1970-01-01T00:02:03Z")
        self.assertEqual(index["phantom-blade-zero"]["last_progress"], entries[-1])
        self.assertEqual(index["witcher3"]["status"], "not_fetched")

    def test_partial_update_keeps_failed_games_and_updates_others(self):
        self.update(["ror2"], game_payload("ror2"))
        previous = (self.data_dir / "achievements.json").read_bytes()
        status, _ = self.update(["ror2", "witcher3"], {}, game_payload("witcher3"))
        self.assertEqual(status, tracker.PARTIAL_SUCCESS)
        self.assertEqual((self.data_dir / "achievements.json").read_bytes(), previous)
        self.assertEqual(self.read("index.json")["games"]["witcher3"]["unlocked"], 1)
        self.assertEqual(self.read("journal.json")["entries"][-1]["game"], "witcher3")

    def test_failed_update_leaves_index_and_journal_untouched(self):
        tracker.update_games(GAMES, self.data_dir, [])
        before = {path.name: path.read_bytes() for path in self.data_dir.glob("*.json")}
        status, _ = self.update(["witcher3"], {})
        self.assertEqual(status, 1)
        self.assertEqual({path.name: path.read_bytes() for path in self.data_dir.glob("*.json")}, before)
