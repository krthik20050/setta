"""Portable backups of the owner's editable companion personality only."""
import json
import os
from pathlib import Path
import tempfile

from .character_profile import CharacterProfile


FORMAT = 'setta-personality'
VERSION = 2
MAX_BYTES = 64 * 1024
LIMITS = {'name': 60, 'role': 500, 'custom_instructions': 6000}
LEGACY_FIELDS = set(LIMITS)
CURRENT_FIELDS = LEGACY_FIELDS | {'personalization'}


def _validate_fields(fields: object, version: int = VERSION) -> dict:
    expected = LEGACY_FIELDS if version == 1 else CURRENT_FIELDS
    if not isinstance(fields, dict) or set(fields) != expected:
        raise ValueError('The personality backup contains unsupported fields.')
    clean = {}
    for key, limit in LIMITS.items():
        value = fields[key]
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError(f'{key} must be text up to {limit} characters.')
        clean[key] = value.strip()
    if not clean['name']:
        raise ValueError('Enter a non-empty companion name.')
    if version >= 2:
        preferences = fields['personalization']
        if not isinstance(preferences, dict) or set(preferences) != set(CharacterProfile.PERSONALIZATION_CHOICES):
            raise ValueError('The backup must include all personality preferences.')
        if any(not isinstance(value, str) or value not in CharacterProfile.PERSONALIZATION_CHOICES[key]
               for key, value in preferences.items()):
            raise ValueError('The backup contains an unsupported personality preference.')
        clean['personalization'] = dict(preferences)
    return clean


def export_profile(destination: str | Path, profile_path: str | Path | None = None) -> Path:
    """Write a versioned backup atomically, excluding voice, facts and credentials."""
    source_path = Path(profile_path) if profile_path is not None else None
    profile = CharacterProfile.load(source_path)
    fields = _validate_fields({**{key: profile.data.get(key, 'Amma' if key == 'name' else '')
                               for key in LIMITS}, 'personalization': profile.personalization()})
    destination = Path(destination)
    # Do not replace the live configuration with a backup envelope.
    actual_source = getattr(profile, '_path', None)
    if actual_source and destination.resolve() == Path(actual_source).resolve():
        raise ValueError('Choose a backup file different from the active profile.')
    descriptor, temporary = tempfile.mkstemp(dir=destination.parent, prefix='setta-profile-', suffix='.tmp')
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            json.dump({'format': FORMAT, 'version': VERSION, 'personality': fields},
                      handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return destination


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate field in backup: {key}')
        result[key] = value
    return result


def preview_profile(source: str | Path) -> dict[str, str]:
    """Read and validate without changing settings; the UI must offer an Apply step."""
    with Path(source).open('rb') as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('This personality backup is too large (maximum 64 KB).')
    try:
        document = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('Choose a valid Setta personality JSON backup.') from exc
    if not isinstance(document, dict) or set(document) != {'format', 'version', 'personality'}:
        raise ValueError('This file is not a Setta personality backup.')
    if document['format'] != FORMAT or type(document['version']) is not int or document['version'] not in {1, VERSION}:
        raise ValueError('This personality backup format or version is not supported.')
    return _validate_fields(document['personality'], document['version'])


def apply_profile(fields: dict[str, str], profile_path: str | Path | None = None) -> CharacterProfile:
    """Apply reviewed fields, preserving every unrelated live configuration field."""
    target = Path(profile_path) if profile_path is not None else None
    version = 1 if isinstance(fields, dict) and set(fields) == LEGACY_FIELDS else VERSION
    return CharacterProfile.save_personality(_validate_fields(fields, version), target)
