import json
import unittest

import httpx

from src.sarvam_conversation import RecognizedTurn, SarvamConversation


class GroqReplyTests(unittest.TestCase):
    def test_voice_bubble_keeps_user_and_current_spoken_reply_labels(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from src.app import PetApp
        app = SimpleNamespace(show_speech_bubble=Mock(), voice_agent=SimpleNamespace(active=True))
        PetApp._voice_show_transcript(app, 'Can we speak English?')
        self.assertIn('You: Can we speak English?', app.show_speech_bubble.call_args.args[0])
        PetApp._voice_show_text(app, 'Of course.')
        self.assertEqual(app.show_speech_bubble.call_args.args[0],
                         'You: Can we speak English?\nAmma: Of course.')
        PetApp._voice_show_final(app, 'Of course.')
        self.assertIsNone(app.show_speech_bubble.call_args.kwargs['duration'])

    def test_spoken_reply_control_toggles_existing_mute_setting(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from src.app import PetApp
        app=SimpleNamespace(voice_agent=SimpleNamespace(muted=True),show_speech_bubble=Mock())
        PetApp._toggle_spoken_replies(app)
        self.assertFalse(app.voice_agent.muted)
        PetApp._toggle_spoken_replies(app)
        self.assertTrue(app.voice_agent.muted)

    def test_groq_selection_and_credential_isolation(self):
        def handler(request):
            self.assertEqual(request.url.host,'api.groq.com')
            self.assertEqual(request.url.path,'/openai/v1/chat/completions')
            self.assertEqual(request.headers['authorization'],'Bearer fake-groq')
            self.assertNotIn('api-subscription-key',request.headers)
            payload=json.loads(request.content)
            self.assertIn('Malayalam',payload['messages'][0]['content'])
            self.assertEqual(payload['reasoning_effort'],'low')
            return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':'നമുക്ക് പഠിക്കാം.'}}]})
        c=SarvamConversation('fake-sarvam',transport=httpx.MockTransport(handler),
            groq_api_key='fake-groq',openai_api_key='fake-openai',reply_provider='groq')
        self.addCleanup(c.close)
        self.assertEqual(c.reply(RecognizedTurn('പഠിക്കാം','ml-IN',None,False)),'നമുക്ക് പഠിക്കാം.')
        self.assertEqual(c.reply_provider,'groq')

    def test_incomplete_reasoning_reply_is_rejected(self):
        c=SarvamConversation('fake-sarvam',transport=httpx.MockTransport(lambda _:httpx.Response(200,
            json={'choices':[{'finish_reason':'length','message':{'content':'partial'}}]})),
            groq_api_key='fake-groq',openai_api_key='',reply_provider='groq')
        self.addCleanup(c.close)
        with self.assertRaises(ValueError): c.reply(RecognizedTurn('Hello','en-IN',None,False))
        self.assertEqual(c.history,[])

    def test_groq_errors_do_not_fallback_or_expose_secrets(self):
        calls=[]
        def handler(request):
            calls.append(request.url.host)
            return httpx.Response(429,text='fake-groq secret provider response')
        c=SarvamConversation('fake-sarvam',transport=httpx.MockTransport(handler),
            groq_api_key='fake-groq',openai_api_key='fake-openai',reply_provider='groq')
        self.addCleanup(c.close)
        with self.assertRaises(RuntimeError) as caught: c.reply(RecognizedTurn('Hello','en-IN',None,False))
        self.assertNotIn('fake-groq',str(caught.exception))
        self.assertEqual(calls,['api.groq.com'])
