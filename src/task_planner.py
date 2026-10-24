"""Small deterministic planner for the first multi-step desktop workflow."""
import re

from .skill_registry import DEFAULT_SKILLS
from .task_execution import TaskPlan, TaskStep


def select_media_service(text: str, available_apps=None) -> str | None:
    """Choose a media service from explicit signals, task type and availability."""
    value = text.casefold()
    apps = set(available_apps or ())
    wants_youtube = bool(re.search(r'\b(?:you\s*tube|u\s*tube|utube|music video|video)\b', value))
    wants_spotify = bool(re.search(r'\bspotify\b', value))
    if wants_youtube and not wants_spotify:
        return 'youtube'
    if wants_spotify:
        return 'spotify'
    # Audio-only requests are best handled by a music app; prefer Spotify.
    if 'spotify' in apps:
        return 'spotify'
    if 'brave' in apps or not apps:
        return 'youtube'
    return None


def plan_request(text: str, available_apps=None) -> TaskPlan | None:
    value = text.strip()
    if not re.search(r'\b(?:play|put on|listen to)\b', value, re.I):
        return None
    if not re.search(r'\b(?:you\s*tube|u\s*tube|utube|spotify|music|song|playlist)\b', value, re.I):
        return None
    match = re.search(r'\b(?:play|put on|listen to)\s+(.+?)(?:\s+on\s+(?:you\s*tube|u\s*tube|utube|spotify|brave)|$)', value, re.I)
    query = match.group(1).strip(' .,!?') if match else 'music'
    query = re.sub(r'^(?:some|a|the)\s+', '', query, flags=re.I).strip() or 'music'
    service = select_media_service(value, available_apps)
    if service is None:
        return None
    skill_name = 'play-youtube-media' if service == 'youtube' else 'play-spotify-media'
    skill = DEFAULT_SKILLS.get(skill_name)
    tool = 'play_youtube_music' if skill_name == 'play-youtube-media' else 'play_spotify_music'
    return TaskPlan(skill, (
        TaskStep(
            'play-media',
            tool,
            {'query': query},
            verifier=lambda result: result.get('status') in {'completed', 'unverified'},
        ),
    ))
