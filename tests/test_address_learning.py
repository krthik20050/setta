import unittest
import tempfile
from pathlib import Path
import io
import wave
import base64
import httpx
from src.character_profile import CharacterProfile
from src.sarvam_conversation import localized_address,SarvamConversation,RecognizedTurn
from src.address_preferences import address_request,resolve_address,MONE
from src.companion_memory import CompanionMemory
from src.companion_context import ConversationSession


class AddressLearningTests(unittest.TestCase):
    def test_explicit_mone_is_not_translated_when_the_sentence_is_english(self):
        profile=CharacterProfile({})
        profile.address_preference={'term':'mone','scope':'once'}
        self.assertEqual(localized_address('Mone, I am here.','en-IN',profile),'mone, I am here.')

    def test_once_is_not_saved_but_durable_preference_survives_restart(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            path=Path(folder)/'memory.sqlite'
            memory=CompanionMemory(path)
            session=ConversationSession(memory,'one')
            session.turn('Call me mone once','en-IN',lambda text,lang,bundle:bundle['address_request']['term'])
            self.assertEqual(memory.facts(),[])
            session.turn('Call me mone in English','en-IN',lambda *args:'Okay, mone.')
            reopened=CompanionMemory(path)
            self.assertEqual(resolve_address(reopened.facts(),'en-IN')['term'],'mone')
            self.assertIsNone(resolve_address(reopened.facts(),'hi-IN'))
            self.assertTrue(reopened.facts()[0]['source_message_id'])

    def test_quoted_or_past_statement_does_not_change_preferences(self):
        for text in ['He said call me mone','I asked her to call me mone once','What does call me mone mean?', 'Call me tomorrow', 'Call me later']:
            self.assertIsNone(address_request(text,'en-IN'))
        self.assertEqual(address_request('Call me monwe once','en-IN')['term'],'mone')

    def test_mone_is_synthesized_in_malayalam_using_the_selected_english_clone(self):
        buffer=io.BytesIO()
        with wave.open(buffer,'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000); wav.writeframes(b'\0\0'*240)
        requests=[]
        def handle(request):
            requests.append(request.content)
            return httpx.Response(200,json={'audio_b64':base64.b64encode(buffer.getvalue()).decode()})
        c=SarvamConversation('test',groq_api_key='',openai_api_key='',reply_provider='sarvam',transport=httpx.MockTransport(handle))
        try:
            c.profile.address_preference={'term':'mone','scope':'once'}
            turn=RecognizedTurn('Call me mone once','en-IN',None,False)
            voice=c.voice_for(turn)[0]
            c.synthesize('mone.',turn)
            self.assertIn(MONE.encode(),requests[0])
            self.assertIn(b'ml-IN',requests[0])
            self.assertIn(voice.encode(),requests[0])
            self.assertNotIn(b'\r\nson\r\n',requests[0])
        finally:c.close()
