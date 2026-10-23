from pathlib import Path
import tempfile
import unittest

from src.companion_memory import CompanionMemory
from src.companion_context import CompanionContext, ConversationSession, InteractionTiming, Observation


class MemoryTests(unittest.TestCase):
    def setUp(self):
        test_root = Path(__file__).resolve().parents[1] / 'runtime' / 'memory-tests'
        test_root.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=test_root)
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'memory.sqlite'
        self.memory = CompanionMemory(self.path)

    def test_recall_survives_restart_and_keeps_source(self):
        identity = self.memory.add_message('yesterday', 'user', 'My project is FloodRoute', 'en-IN')
        reopened = CompanionMemory(self.path)
        hit = reopened.search('FloodRoute')[0]
        self.assertEqual(hit['id'], identity)
        self.assertEqual(hit['source'], 'mother_chat')
        self.assertTrue(hit['created_at'])
        self.assertEqual(reopened.recent(2)[0]['text'], 'My project is FloodRoute')

    def test_unicode_search_and_query_punctuation(self):
        self.memory.add_message('a', 'user', 'എനിക്ക് മലയാളം ഇഷ്ടമാണ്', 'ml-IN')
        self.assertTrue(self.memory.search('മലയാളം'))
        self.memory.search('" OR * --')
        self.assertEqual(self.memory.search(''), [])

    def test_user_fact_correction_and_forgetting(self):
        first = self.memory.add_message('a', 'user', 'Call me Karthik')
        self.memory.remember('preferred_name', 'Karthik', first)
        second = self.memory.add_message('a', 'user', 'Actually call me K')
        self.memory.remember('preferred_name', 'K', second)
        self.assertEqual(self.memory.facts()[0]['value'], 'K')
        self.memory.delete_message(second)
        self.assertEqual(self.memory.facts(), [])
        self.assertFalse(self.memory.search('Actually'))

    def test_assistant_cannot_confirm_user_fact(self):
        source = self.memory.add_message('a', 'assistant', 'You seem sad')
        with self.assertRaises(ValueError):
            self.memory.remember('mood', 'sad', source)

    def test_replayed_message_deduplicates_and_conflict_rejected(self):
        first = self.memory.add_message('a', 'user', 'Hello', external_id='turn1')
        self.assertEqual(self.memory.add_message('a', 'user', 'Hello', external_id='turn1'), first)
        with self.assertRaises(ValueError):
            self.memory.add_message('a', 'user', 'Different', external_id='turn1')

    def test_context_expires_observations_not_memories(self):
        self.memory.add_message('old', 'user', 'Finish my prototype')
        observations = [Observation('jaw', 'possible yawn', 'camera', .8, 10),
                        Observation('eyes', 'closed', 'camera', .8, 19)]
        bundle = CompanionContext(self.memory).prepare('prototype', 'new', observations, now=20)
        self.assertEqual(len(bundle['observations']), 1)
        self.assertEqual(bundle['observations'][0]['kind'], 'eyes')
        self.assertTrue(bundle['relevant'])
        self.assertTrue(bundle['recent_other_sessions'])
        self.assertIn('external_messages', bundle['missing_sources'])

    def test_provider_gets_memory_and_failed_reply_is_not_stored(self):
        session = ConversationSession(self.memory, 'a')
        session.turn('My exam is Friday', 'en-IN', lambda text, language, context: 'I will keep that in mind.')
        def respond(text, language, context):
            self.assertEqual(language, 'ml-IN')
            self.assertIn('Friday', context['recent'][0]['text'])
            raise RuntimeError('offline')
        with self.assertRaises(RuntimeError):
            session.turn('When is my exam?', 'ml-IN', respond)
        self.assertEqual([m['role'] for m in self.memory.recent()], ['user', 'assistant', 'user'])

    def test_delete_removes_search_and_export_preserves_unicode(self):
        import json
        message = self.memory.add_message('a', 'user', 'മലയാളം')
        export = Path(self.directory.name) / 'export.json'
        self.memory.export(export)
        self.assertEqual(json.loads(export.read_text(encoding='utf-8'))['messages'][0]['text'], 'മലയാളം')
        self.memory.delete_message(message)
        self.assertEqual(self.memory.search('മലയാളം'), [])


class TimingTests(unittest.TestCase):
    def test_audio_muted_desktop_actions_explicit_and_checkins_rate_limited(self):
        timing = InteractionTiming()
        self.assertFalse(timing.may_speak())
        self.assertFalse(timing.may_act(user_requested=False, action_authorized=True))
        self.assertFalse(timing.may_act(user_requested=True, action_authorized=False))
        self.assertTrue(timing.may_act(user_requested=True, action_authorized=True))
        self.assertTrue(timing.may_check_in(0, True, True))
        timing.mark_check_in(0)
        self.assertFalse(timing.may_check_in(60, True, True))
        self.assertFalse(timing.may_check_in(180, False, True))
        timing.user_speaking = True
        self.assertFalse(timing.may_check_in(180, True, True))
