import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import httpx

from src.camera_context import asks_about_eyewear, eyewear_observation
from src.desktop_context import desktop_observations
from src.companion_memory import CompanionMemory
from src.companion_context import ConversationSession


class ContextFeatureTests(unittest.TestCase):
    def test_clock_and_process_name_are_fresh_without_screen_or_file_access(self):
        with patch('src.desktop_context.foreground_app', return_value='Code.exe') as app:
            observations = desktop_observations({'date_time': True, 'foreground_app': True})
            self.assertEqual(observations[1].value, 'Code.exe')
            self.assertIn('T', observations[0].value)
            self.assertEqual(observations[1].ttl, 5)
            app.assert_called_once()
        with patch('src.desktop_context.foreground_app') as app:
            self.assertEqual(desktop_observations({'date_time':False, 'foreground_app':False}), [])
            app.assert_not_called()

    def test_eyewear_only_for_an_explicit_relevant_question(self):
        self.assertTrue(asks_about_eyewear('Am I wearing specs?'))
        self.assertTrue(asks_about_eyewear('Ente kannadi kaanamo?'))
        self.assertFalse(asks_about_eyewear('How was your day?'))

    def test_vision_sends_only_the_provided_crop_and_bounds_the_result(self):
        def handle(request):
            data = json.loads(request.content)
            url = data['messages'][0]['content'][1]['image_url']['url']
            self.assertEqual(base64.b64decode(url.split(',')[1]), b'cropped-jpeg')
            self.assertEqual(data['model'], 'vision-test')
            return httpx.Response(200, json={'choices':[{'finish_reason':'stop',
                'message':{'content':'{"glasses":"present"}'}}]})
        with httpx.Client(base_url='https://example.test', transport=httpx.MockTransport(handle)) as client:
            result = eyewear_observation(client, 'vision-test', b'cropped-jpeg')
        self.assertIn('present', result.value)
        self.assertIn('may be wrong', result.value)
        self.assertEqual(result.ttl, 15)
        self.assertIn('Unknown', eyewear_observation(None, '', None).value)

    def test_explicit_facts_survive_restart_and_can_be_removed(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            path = Path(folder)/'memory.sqlite'
            session = ConversationSession(CompanionMemory(path), 'first')
            session.turn('remember: response_style = concise and practical', 'en-IN', lambda *args:'Saved.')
            reopened = CompanionMemory(path)
            self.assertEqual(reopened.facts()[0]['value'], 'concise and practical')
            session = ConversationSession(reopened, 'restart')
            def respond(text, language, bundle):
                self.assertEqual(bundle['memory_action']['status'], 'removed_from_confirmed_facts')
                return 'Removed from confirmed facts; chat history is retained.'
            session.turn('forget: response_style', 'en-IN', respond)
            self.assertEqual(CompanionMemory(path).facts(), [])

    def test_explicit_spoken_remember_does_not_need_punctuation(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            memory = CompanionMemory(Path(folder)/'memory.sqlite')
            session = ConversationSession(memory, 'voice')
            session.turn('Remember that I prefer short practical replies.', 'en-IN', lambda *args: 'Got it.')
            self.assertEqual(memory.facts()[0]['value'], 'I prefer short practical replies')
