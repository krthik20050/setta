from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

from src.character_profile import CharacterProfile, RecognitionGreeting
from src.sarvam_voice import SarvamVoiceAgent


class CharacterProfileTests(unittest.TestCase):
    def test_manglish_greeting_renders_for_speech_without_fake_memory_turn(self):
        agent = SarvamVoiceAgent('test')
        conversation = MagicMock()
        with patch('src.sarvam_voice.LiveConversation', return_value=conversation), \
             patch('src.sarvam_voice.SarvamConversation.reply', return_value='മോനേ, സുഖമാണോ?') as render, \
             patch.object(agent, '_play'):
            agent._greet('Mone, sukhamaano?', 'ml-IN')
        render.assert_called_once()
        conversation.reply.assert_not_called()
        conversation.memory.add_message.assert_called_once_with(
            conversation.session.session_id, 'assistant', 'മോനേ, സുഖമാണോ?', 'ml-IN')
        conversation.close.assert_called_once()

    def test_affectionate_address_changes_with_each_language(self):
        profile = CharacterProfile({'address_user': 'mone', 'address_by_language': {
            'ml-IN': 'mone', 'hi-IN': 'beta', 'en-IN': 'son'}})
        for language, address in [('ml-IN', 'mone'), ('hi-IN', 'beta'), ('en-IN', 'son')]:
            self.assertIn(f'For this turn, address the user as {address}', profile.instructions(language))

    def test_wrong_language_pet_name_is_corrected_without_touching_words(self):
        from src.sarvam_conversation import localized_address
        profile = CharacterProfile({})
        self.assertEqual(localized_address('Well done, beta! Betamax works.', 'en-IN', profile),
                         'Well done, son! Betamax works.')
        self.assertEqual(localized_address('Mone, great!', 'hi-IN', profile), 'बेटा, great!')

    def test_editable_profiles_have_no_malayalam_script(self):
        from src.paths import PROJECT_ROOT
        for name in ['amma.json', 'amma.example.json']:
            text = (PROJECT_ROOT/'config'/name).read_text(encoding='utf-8')
            self.assertFalse(any('\u0d00' <= c <= '\u0d7f' for c in text))

    def test_profile_prompt_uses_name_address_and_confirmed_facts(self):
        p=CharacterProfile({'name':'Amma','role':'caring mother','address_user':'മോനേ',
                            'confirmed_facts':{'favourite_food':'idli'},'custom_instructions':'Be gentle.'})
        text=p.instructions()
        for part in ['Amma','മോനേ','idli','Be gentle.','Never invent shared family memories']:
            self.assertIn(part,text)
        self.assertIn('not a formal service assistant',text)

    def test_only_confirmed_owner_can_trigger_after_two_consecutive_matches(self):
        gate=RecognitionGreeting({'enabled':True,'owner_face_label':'karthik'})
        self.assertFalse(gate.consider('papa',0))
        self.assertFalse(gate.consider('Unknown',1))
        self.assertFalse(gate.consider('karthik',2))
        self.assertFalse(gate.consider('papa',3))
        self.assertFalse(gate.consider('karthik',4))
        self.assertTrue(gate.consider('karthik',5))

    def test_presence_never_repeats_and_return_requires_absence_and_cooldown(self):
        gate=RecognitionGreeting({'enabled':True,'owner_face_label':'karthik','cooldown_seconds':600})
        gate.consider('karthik',0);self.assertTrue(gate.consider('karthik',1));gate.mark_greeted(1)
        for i in range(2,700): self.assertFalse(gate.consider('karthik',i))
        self.assertFalse(gate.consider('karthik',740))
        self.assertTrue(gate.consider('karthik',741))

    def test_short_look_away_and_busy_state_do_not_cause_repeated_speech(self):
        gate=RecognitionGreeting({'enabled':True,'owner_face_label':'karthik'})
        gate.consider('karthik',0)
        self.assertFalse(gate.consider('karthik',1,busy=True))
        self.assertTrue(gate.consider('karthik',2))
        gate.mark_greeted(2)
        gate.consider('Unknown',5)
        self.assertFalse(gate.consider('karthik',10))
        self.assertFalse(gate.consider('karthik',11))

    def test_greeting_does_not_open_microphone_or_start_when_busy_muted(self):
        agent=SarvamVoiceAgent('test');agent.muted=True
        with patch('src.sarvam_voice.threading.Thread') as thread, patch('src.sarvam_voice.sr.Microphone') as mic:
            self.assertFalse(agent.say_greeting('ഹലോ'))
            thread.assert_not_called();mic.assert_not_called()
            agent.muted=False
            self.assertTrue(agent.say_greeting('ഹലോ'))
            thread.assert_called_once();mic.assert_not_called()
