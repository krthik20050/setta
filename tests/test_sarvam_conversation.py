import base64
import io
import json
import re
import unittest
import wave

import httpx

from src.sarvam_conversation import SarvamConversation, RecognizedTurn, compact_reply, mixed_malayalam, speech_chunks


def wav_bytes():
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(b'\0\0'*2400)
    return buffer.getvalue()


class ConversationTests(unittest.TestCase):
    def test_provider_output_is_compacted_for_spoken_turns(self):
        text = 'Okay. ' + 'This is extra detail that is not needed. ' * 8
        result = compact_reply(text)
        self.assertLessEqual(len(result.split()), 45)
        self.assertLessEqual(len(re.findall(r'[.!?।॥]', result)), 2)

    def conversation(self, handler):
        client = SarvamConversation('fake-test-key', transport=httpx.MockTransport(handler), openai_api_key='')
        self.addCleanup(client.close)
        return client

    def test_auto_detection_preserves_native_and_english_words(self):
        def handler(request):
            self.assertEqual(request.url.path, '/speech-to-text')
            self.assertIn(b'unknown', request.content)
            self.assertIn(b'codemix', request.content)
            return httpx.Response(200, json={'transcript':'ഇന്ന് English പഠിക്കാം', 'language_code':'ml-IN'})
        turn = self.conversation(handler).recognize(wav_bytes())
        self.assertTrue(turn.mixed)
        self.assertEqual(turn.language, 'ml-IN')

    def test_languages_can_switch_each_turn(self):
        replies = iter([('ഹലോ','ml-IN'),('Hello','en-IN'),('नमस्ते','hi-IN')])
        def handler(request):
            text, lang = next(replies)
            return httpx.Response(200, json={'transcript':text,'language_code':lang})
        client = self.conversation(handler)
        self.assertEqual([client.recognize(wav_bytes()).language for _ in range(3)],['ml-IN','en-IN','hi-IN'])

    def test_empty_and_unsupported_transcripts(self):
        c = self.conversation(lambda _:httpx.Response(200,json={'transcript':''}))
        self.assertIsNone(c.recognize(wav_bytes()))
        c = self.conversation(lambda _:httpx.Response(200,json={'transcript':'Bonjour','language_code':'fr-FR'}))
        with self.assertRaises(ValueError): c.recognize(wav_bytes())

    def test_selected_voice_routing(self):
        c = self.conversation(lambda _:httpx.Response(200,json={}))
        pure = RecognizedTurn('ഇന്ന് പഠിക്കാം','ml-IN',None,False)
        mixed = RecognizedTurn('English പഠിക്കാം','ml-IN',None,True)
        self.assertEqual(c.voice_for(pure)[1],8)
        self.assertEqual(c.voice_for(mixed)[1],6)
        self.assertEqual(c.voice_for(pure,'ഇന്ന് homework ചെയ്യാം')[1],6)

    def test_prompt_requests_same_language_brief_no_fillers(self):
        def handler(request):
            body = json.loads(request.content)
            self.assertEqual(request.url.path,'/v1/chat/completions')
            self.assertIn('Malayalam',body['messages'][0]['content'])
            self.assertIn('filler',body['messages'][0]['content'])
            self.assertEqual(body['max_tokens'],350)
            self.assertIsNone(body['reasoning_effort'])
            return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':'നമുക്ക് പഠിക്കാം.'}}]})
        c = self.conversation(handler)
        self.assertEqual(c.reply(RecognizedTurn('പഠിക്കാം','ml-IN',None,False)),'നമുക്ക് പഠിക്കാം.')
        self.assertEqual(len(c.history),2)

    def test_incomplete_and_wrong_language_responses_not_spoken(self):
        for reason,text in [('length','നമുക്ക്'),('stop','English only')]:
            c = self.conversation(lambda _, reason=reason,text=text:httpx.Response(200,json={
                'choices':[{'finish_reason':reason,'message':{'content':text}}]}))
            with self.assertRaises(ValueError): c.reply(RecognizedTurn('ഹലോ','ml-IN',None,False))
            self.assertEqual(c.history,[])

    def test_synthesis_is_multipart_uses_selected_voice(self):
        def handler(request):
            self.assertIn(b'voice_id',request.content)
            self.assertIn(b'ml-IN',request.content)
            self.assertIn(b'true',request.content)
            self.assertIn(b'name="pace"',request.content)
            self.assertIn(b'1.18',request.content)
            self.assertIn(b'name="enable_vad"',request.content)
            return httpx.Response(200,json={'audio_b64':base64.b64encode(wav_bytes()).decode()})
        c=self.conversation(handler)
        self.assertEqual(c.synthesize('ഹലോ',RecognizedTurn('ഹലോ','ml-IN',None,False)),wav_bytes())

    def test_pace_is_editable_and_invalid_pace_never_calls_provider(self):
        requests = []
        def handler(request):
            requests.append(request)
            self.assertIn(b'1.25', request.content)
            return httpx.Response(200,json={'audio_b64':base64.b64encode(wav_bytes()).decode()})
        c = self.conversation(handler)
        c.profile.data['speech_delivery'] = {'pace': 1.25}
        turn = RecognizedTurn('Hello', 'en-IN', None, False)
        c.synthesize('Hello', turn)
        c.profile.data['speech_delivery']['pace'] = 3
        with self.assertRaises(ValueError):
            c.synthesize('Hello', turn)
        self.assertEqual(len(requests), 1)

    def test_provider_error_does_not_expose_key_or_response_body(self):
        c = self.conversation(lambda _:httpx.Response(403,text='fake-test-key private provider data'))
        with self.assertRaises(RuntimeError) as caught: c.recognize(wav_bytes())
        self.assertNotIn('fake-test-key',str(caught.exception))
        self.assertNotIn('private provider data',str(caught.exception))

    def test_chunks_preserve_all_words_and_bound_lengths(self):
        text = 'ആദ്യം പഠിക്കാം. ' + 'English മലയാളം ' * 40
        chunks=speech_chunks(text,80)
        self.assertTrue(all(len(x)<=80 for x in chunks))
        self.assertEqual(' '.join(chunks).split(),text.split())

    def test_script_detection_and_ambiguous_language_fallback(self):
        self.assertTrue(mixed_malayalam('ഇന്ന് English'))
        self.assertFalse(mixed_malayalam('ഇന്ന് പഠിക്കാം'))
        c=self.conversation(lambda _:httpx.Response(200,json={'transcript':'ഹലോ','language_code':'en-IN'}))
        self.assertEqual(c.recognize(wav_bytes()).language,'ml-IN')

    def test_openai_reply_uses_separate_credentials_and_native_prompt(self):
        def handler(request):
            self.assertEqual(request.url.host,'api.openai.com')
            self.assertEqual(request.url.path,'/v1/responses')
            self.assertEqual(request.headers['authorization'],'Bearer openai-test-only')
            self.assertNotIn('api-subscription-key',request.headers)
            body=json.loads(request.content)
            self.assertFalse(body['store'])
            self.assertIn('Malayalam',body['instructions'])
            return httpx.Response(200,json={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'നമുക്ക് പഠിക്കാം.'}]}]})
        c=SarvamConversation('fake-sarvam-key',transport=httpx.MockTransport(handler),openai_api_key='openai-test-only')
        self.addCleanup(c.close)
        self.assertEqual(c.reply(RecognizedTurn('ഹലോ','ml-IN',None,False)),'നമുക്ക് പഠിക്കാം.')

    def test_openai_failure_is_sanitized_and_not_silently_rerouted(self):
        calls=[]
        def handler(request):
            calls.append(request.url.host)
            return httpx.Response(401,text='openai-test-only private body')
        c=SarvamConversation('fake-sarvam-key',transport=httpx.MockTransport(handler),openai_api_key='openai-test-only')
        self.addCleanup(c.close)
        with self.assertRaises(RuntimeError) as caught: c.reply(RecognizedTurn('Hello','en-IN',None,False))
        self.assertNotIn('openai-test-only',str(caught.exception))
        self.assertEqual(calls,['api.openai.com'])


if __name__=='__main__':
    unittest.main()
