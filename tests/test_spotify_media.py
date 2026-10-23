import unittest
from pathlib import Path
from unittest.mock import Mock

from src.spotify_media import SpotifyMedia


class SpotifyMediaTests(unittest.TestCase):
    def test_search_opens_spotify_and_reports_unverified_playback(self):
        launcher = Mock()
        result = SpotifyMedia(Path('Spotify.exe'), launcher).search('relaxing music')
        self.assertEqual(result['status'], 'unverified')
        self.assertEqual(launcher.call_count, 2)
        self.assertTrue(launcher.call_args_list[1].args[0].startswith('spotify:search:'))


if __name__ == '__main__':
    unittest.main()
