import json
from pathlib import Path
import tempfile
import unittest

from src.paths import PROJECT_ROOT
from src.profile_backup import apply_profile, export_profile, preview_profile, MAX_BYTES


class ProfileBackupTests(unittest.TestCase):
    def setUp(self):
        parent = PROJECT_ROOT / 'runtime' / 'profile-backup-tests'
        parent.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.profile = self.root / 'amma.json'
        self.initial = {'name': 'Amma', 'role': 'Mother', 'custom_instructions': 'Be kind.',
                        'api_key': 'private', 'confirmed_facts': {'family': 'private'},
                        'voice': {'provider': 'preserve'}, 'future': [1, 2]}
        self.profile.write_text(json.dumps(self.initial), encoding='utf-8')
        self.backup = self.root / 'backup.json'

    def document(self, **updates):
        document = {'format': 'setta-personality', 'version': 1,
                    'personality': {key: self.initial[key] for key in ('name', 'role', 'custom_instructions')}}
        document.update(updates)
        self.backup.write_text(json.dumps(document), encoding='utf-8')

    def test_roundtrip_excludes_private_data_preview_does_not_apply_and_apply_preserves_config(self):
        export_profile(self.backup, self.profile)
        raw = self.backup.read_text(encoding='utf-8')
        self.assertNotIn('private', raw)
        self.assertNotIn('voice', raw)
        fields = preview_profile(self.backup)
        fields['name'] = 'Mama'
        self.assertEqual(json.loads(self.profile.read_text()), self.initial)
        result = apply_profile(fields, self.profile)
        self.assertEqual(result.name, 'Mama')
        expected = dict(self.initial, name='Mama')
        self.assertEqual(json.loads(self.profile.read_text()), expected)

    def test_export_cannot_overwrite_active_profile(self):
        with self.assertRaises(ValueError):
            export_profile(self.profile, self.profile)
        self.assertEqual(json.loads(self.profile.read_text()), self.initial)

    def test_unknown_formats_versions_fields_and_invalid_values_are_rejected(self):
        for updates in ({'format': 'other'}, {'version': 2}, {'version': True}, {'extra': 'secret'},
                        {'personality': {'name': 'Amma'}},
                        {'personality': {'name': ' ', 'role': '', 'custom_instructions': ''}},
                        {'personality': {'name': 'x' * 61, 'role': '', 'custom_instructions': ''}},
                        {'personality': {'name': 'Amma', 'role': 9, 'custom_instructions': ''}}):
            with self.subTest(updates=updates):
                self.document(**updates)
                with self.assertRaises(ValueError):
                    preview_profile(self.backup)

    def test_malformed_duplicate_and_large_files_are_rejected(self):
        for raw in (b'not json', b'\xff', b'{"format":1,"format":2}', b' ' * (MAX_BYTES + 1)):
            self.backup.write_bytes(raw)
            with self.assertRaises(ValueError):
                preview_profile(self.backup)

    def test_apply_revalidates_fields_and_does_not_mutate_on_failure(self):
        with self.assertRaises(ValueError):
            apply_profile({'name': 'Mama', 'role': 'Mother', 'custom_instructions': '', 'voice': 'replace'}, self.profile)
        self.assertEqual(json.loads(self.profile.read_text()), self.initial)

    def test_unicode_and_length_boundaries(self):
        fields = {'name': 'അമ്മ', 'role': 'r' * 500, 'custom_instructions': 'c' * 6000}
        apply_profile(fields, self.profile)
        export_profile(self.backup, self.profile)
        self.assertEqual(preview_profile(self.backup), fields)
