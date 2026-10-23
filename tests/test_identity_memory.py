from pathlib import Path
import tempfile
import unittest
from src.companion_memory import CompanionMemory
from src.companion_context import CompanionContext, ConversationSession
from src.agent_tools import DesktopTools


class IdentityMemoryTests(unittest.TestCase):
    def test_identity_and_home_survive_new_session_with_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'memory.sqlite'
            first = ConversationSession(CompanionMemory(path), 'one')
            first.turn('My name is Test Person.', 'en-IN', lambda *args: 'Okay.')
            first.turn('I live in Test City.', 'en-IN', lambda *args: 'Okay.')
            reopened = CompanionMemory(path)
            facts = {row['key']:row for row in reopened.facts()}
            self.assertEqual(facts['user_name']['value'], 'Test Person')
            self.assertEqual(facts['home_location']['value'], 'Test City')
            context = CompanionContext(reopened).prepare('What is my name?', 'two')
            self.assertEqual(len(context['confirmed_facts']), 2)
            self.assertTrue(all(row['source_message_id'] for row in context['confirmed_facts']))
            tools = DesktopTools(memory=reopened, launcher=lambda p: None)
            result = tools.execute('search_conversation_memory', {'query':'Test City'}, 'Where did I say I live?')
            self.assertTrue(any('Test City' in row['text'] for row in result['results']))

    def test_quoted_or_third_person_claim_is_not_promoted_to_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            memory = CompanionMemory(Path(folder)/'memory.sqlite')
            session = ConversationSession(memory, 'one')
            for text in ['She said my name is Example', 'Call me tomorrow', 'What if my name is Example?']:
                session.turn(text, 'en-IN', lambda *args: 'Okay.')
            self.assertEqual(memory.facts(), [])
