import unittest

from netease_to_apple_music import (
    SourceTrack,
    classify_score,
    normalize_text,
    parse_playlist_id,
    score_candidate,
    unique_track_ids,
)


class PlaylistIdTests(unittest.TestCase):
    def test_numeric_id(self):
        self.assertEqual(parse_playlist_id("123456"), "123456")

    def test_share_url(self):
        self.assertEqual(
            parse_playlist_id("分享：https://music.163.com/playlist?id=98765&userid=1"),
            "98765",
        )

    def test_hash_url(self):
        self.assertEqual(
            parse_playlist_id("https://music.163.com/#/playlist?id=24680"),
            "24680",
        )


class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.source = SourceTrack(
            id="1",
            name="Example Song",
            artists=("Example Artist",),
            album="Example Album",
            duration_ms=210_000,
        )

    def test_normalization(self):
        self.assertEqual(normalize_text(" Example—Song（Live） "), "examplesonglive")

    def test_traditional_chinese_normalizes_to_simplified(self):
        self.assertEqual(normalize_text("愛人錯過"), normalize_text("爱人错过"))

    def test_exact_candidate_scores_high(self):
        candidate = {
            "attributes": {
                "name": "Example Song",
                "artistName": "Example Artist",
                "albumName": "Example Album",
                "durationInMillis": 211_000,
            }
        }
        self.assertGreaterEqual(score_candidate(self.source, candidate), 95)

    def test_wrong_live_version_is_penalized(self):
        candidate = {
            "attributes": {
                "name": "Example Song (Live)",
                "artistName": "Example Artist",
                "albumName": "Example Album (Live)",
                "durationInMillis": 210_000,
            }
        }
        self.assertLess(score_candidate(self.source, candidate), 82)

    def test_localized_artist_can_match_on_strong_metadata(self):
        source = SourceTrack(
            id="2",
            name="爱人错过",
            artists=("告五人",),
            album="我肯定在几百年前就说过爱你",
            duration_ms=292_000,
        )
        candidate = {
            "attributes": {
                "name": "愛人錯過",
                "artistName": "Accusefive",
                "albumName": "我肯定在幾百年前就說過愛你",
                "durationInMillis": 292_075,
            }
        }
        self.assertGreaterEqual(score_candidate(source, candidate), 82)

    def test_classification(self):
        self.assertEqual(classify_score(90, 82, 68), "matched")
        self.assertEqual(classify_score(75, 82, 68), "needs_review")
        self.assertEqual(classify_score(50, 82, 68), "unmatched")

    def test_track_ids_are_deduplicated(self):
        rows = [
            {"status": "matched", "match": {"id": "10"}},
            {"status": "matched", "match": {"id": "10"}},
            {"status": "needs_review", "match": {"id": "11"}},
        ]
        self.assertEqual(unique_track_ids(rows, False), ["10"])
        self.assertEqual(unique_track_ids(rows, True), ["10", "11"])


if __name__ == "__main__":
    unittest.main()
