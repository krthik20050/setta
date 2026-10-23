"""Shared UI preferences and the modern companion window."""
import json
from pathlib import Path
from .paths import DATA_DIR


class HubPreferences:
    """Independent UI preferences; never rewrite the shared voice/profile config."""
    def __init__(self, path=None):
        self.path = Path(path or DATA_DIR / 'hub-settings.json')
        self.values = {'desktop_visible': True, 'walking': True, 'approved_likeness': True,
                       'display_script': 'manglish', 'reduced_motion': False, 'theme': 'light', 'face_candidates': False, 'face_discovery': True}
        try:
            saved = json.loads(self.path.read_text(encoding='utf-8'))
            self.values.update({k: v for k, v in saved.items() if k in self.values and
                ((k == 'display_script' and v in ('manglish', 'native')) or
                 (k == 'theme' and v in ('light', 'dark', 'system')) or
                 (k not in ('display_script', 'theme') and isinstance(v, bool)))})
        except (OSError, ValueError, AttributeError):
            pass

    def save(self, **values):
        updated = {**self.values, **values}
        if any(k not in self.values or (v not in ('light', 'dark', 'system') if k == 'theme' else
                                       v not in ('manglish', 'native') if k == 'display_script'
                                        else not isinstance(v, bool)) for k, v in values.items()):
            raise ValueError('Unknown or invalid setting')
        self.persist(updated)
        self.values = updated

    def persist(self, updated):
        """Write an immutable UI snapshot without changing newer in-memory settings."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(updated, indent=2), encoding='utf-8')
        temporary.replace(self.path)


from .modern_hub import ModernHub as CompanionHub
