"""Bounded visible-browser workflow for YouTube media playback."""
from pathlib import Path
import re
import time
from urllib.parse import quote_plus

from .paths import RUNTIME_DIR


class BrowserMedia:
    def __init__(self, executable: Path, profile_dir: Path | None = None):
        self.executable = Path(executable)
        self.profile_dir = profile_dir or RUNTIME_DIR / 'browser-profile'
        self.context = None
        self.page = None

    def play_youtube(self, query: str) -> dict[str, object]:
        query = query.strip()
        if not query or len(query) > 180:
            raise ValueError('Use a short music request')
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout, Error as PlaywrightError
        except ImportError as error:
            raise RuntimeError('Browser automation is not installed.') from error
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        if self.context is None:
            self._playwright = sync_playwright().start()
            try:
                self.context = self._playwright.chromium.launch_persistent_context(
                    user_data_dir=str(self.profile_dir),
                    executable_path=str(self.executable),
                    headless=False,
                    args=['--autoplay-policy=no-user-gesture-required'],
                )
            except PlaywrightError as error:
                self._playwright.stop()
                self._playwright = None
                return {'status': 'unavailable', 'reason': 'Brave could not be controlled.',
                        'error_type': type(error).__name__}
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        search_url = 'https://www.youtube.com/results?search_query=' + quote_plus(query)
        try:
            self.page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
            self._dismiss_consent()
            result = self.page.locator('a#video-title').first
            result.wait_for(state='visible', timeout=20000)
            title = (result.get_attribute('title') or result.inner_text()).strip()
            result.click()
            self.page.wait_for_url(re.compile(r'youtube\.com/watch'), timeout=20000)
            self.page.locator('video').wait_for(state='attached', timeout=15000)
            self.page.wait_for_timeout(2500)
            playing = bool(self.page.locator('video').evaluate(
                '(video) => !video.paused && video.currentTime > 0'))
            return {'status': 'completed' if playing else 'unverified',
                    'query': query, 'title': title[:200], 'playing': playing}
        except PlaywrightTimeout as error:
            return {'status': 'unavailable', 'reason': 'YouTube did not finish loading or playback was blocked.',
                    'error_type': type(error).__name__}

    def _dismiss_consent(self):
        for label in ('Accept all', 'I agree', 'Reject all'):
            button = self.page.get_by_role('button', name=label, exact=True)
            if button.count():
                try:
                    button.first.click(timeout=1500)
                    return
                except PlaywrightError:
                    pass

    def close(self):
        if self.context is not None:
            self.context.close()
            self.context = None
        if getattr(self, '_playwright', None) is not None:
            self._playwright.stop()
            self._playwright = None
