"""Validated registry for bounded desktop-agent skills.

The registry describes what a skill may use; it does not authorize or execute
desktop actions. Permission checks remain in the existing tool layer.
"""
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class SkillSpec:
    name: str
    description: str
    intents: tuple[str, ...]
    tools: tuple[str, ...]
    permissions: tuple[str, ...]
    max_steps: int = 1
    requires_confirmation: bool = False

    def __post_init__(self):
        if not self.name or not self.description:
            raise ValueError('A skill needs a name and description')
        if not self.intents or not self.tools:
            raise ValueError('A skill needs at least one intent and tool')
        if self.max_steps < 1 or self.max_steps > 32:
            raise ValueError('Skill step limit must be between 1 and 32')
        for value in (*self.intents, *self.tools, *self.permissions):
            if not value or value.strip() != value:
                raise ValueError('Skill identifiers must be non-empty and trimmed')


class SkillRegistry:
    def __init__(self, skills: Iterable[SkillSpec] = ()):
        self._skills: dict[str, SkillSpec] = {}
        for skill in skills:
            self.register(skill)

    def register(self, skill: SkillSpec) -> None:
        if skill.name in self._skills:
            raise ValueError(f'Duplicate skill: {skill.name}')
        self._skills[skill.name] = skill

    def get(self, name: str) -> SkillSpec | None:
        return self._skills.get(name)

    def for_intent(self, intent: str) -> tuple[SkillSpec, ...]:
        return tuple(skill for skill in self._skills.values() if intent in skill.intents)

    def names(self) -> tuple[str, ...]:
        return tuple(self._skills)


DEFAULT_SKILLS = SkillRegistry((
    SkillSpec(
        name='open-app',
        description='Open a supported installed application.',
        intents=('open_app',),
        tools=('open_app',),
        permissions=('desktop_apps',),
    ),
    SkillSpec(
        name='play-youtube-media',
        description='Open a browser, find requested media on YouTube and verify playback.',
        intents=('play_media',),
        tools=('open_app', 'browser_navigate', 'browser_search', 'verify_media_playing',
               'play_youtube_music'),
        permissions=('desktop_apps', 'browser_navigation'),
        max_steps=8,
    ),
    SkillSpec(
        name='play-spotify-media',
        description='Open Spotify and search for requested music.',
        intents=('play_media',),
        tools=('play_spotify_music',),
        permissions=('desktop_apps',),
        max_steps=1,
    ),
))
