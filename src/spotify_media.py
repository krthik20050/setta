"""Bounded Spotify desktop launcher.

Spotify's desktop URI can open a search, but it does not provide a reliable
local playback acknowledgement without an authenticated Web API or UI session.
This adapter therefore reports search-opened as unverified.
"""
from pathlib import Path
from urllib.parse import quote
import os


class SpotifyMedia:
    def __init__(self, executable: Path, launcher=None):
        self.executable = Path(executable)
        self.launcher = launcher or os.startfile

    def search(self, query: str) -> dict[str, object]:
        query = query.strip()
        if not query or len(query) > 180:
            raise ValueError('Use a short music request')
        self.launcher(str(self.executable))
        self.launcher('spotify:search:' + quote(query, safe=''))
        return {'status': 'unverified', 'query': query, 'app': 'spotify',
                'reason': 'Spotify opened the search; playback could not be verified locally.'}
