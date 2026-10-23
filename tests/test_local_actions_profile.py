from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
import json
import httpx

from src.local_actions import calculate,parse_command
from src.local_timers import LocalTimers
from src.character_profile import CharacterProfile
from src.live_conversation import LiveConversation
from src.sarvam_conversation import RecognizedTurn
from src.agent_tools import DesktopTools


class LocalActionsProfileTests(unittest.TestCase):
    def test_parse_command_accepts_discovered_app_names(self):
        self.assertEqual(parse_command('Open Figma', {'figma', 'file_explorer'}), ('open_app', 'figma'))
        self.assertEqual(parse_command('Please launch the file explorer', {'figma', 'file_explorer'}),
                         ('open_app', 'file_explorer'))
        self.assertEqual(parse_command('Open Figma', {'figma'}), ('open_app', 'figma'))
        self.assertEqual(parse_command('Start browser', {'browser'}), ('open_app', 'browser'))
        self.assertEqual(parse_command('Google latest Windows UI Automation', {'browser'}),
                         ('search_browser', 'latest Windows UI Automation'))
        self.assertEqual(parse_command('Hi good morning, then open Docker Desktop', {'docker_desktop'}),
                         ('open_app', 'docker_desktop'))
        self.assertEqual(parse_command('Hi good morning, like open Docker Desktop', {'docker_desktop'}),
                         ('open_app', 'docker_desktop'))

    def test_arithmetic_accepts_numbers_but_never_code_or_unbounded_operations(self):
        self.assertEqual(calculate('245 * 18'),'4410')
        self.assertEqual(calculate('(12 + 3) / 5'),'3')
        for value in ['__import__("os")','2 ** 100','1 / 0','4 +','1e90']:
            with self.assertRaises(ValueError): calculate(value)
        self.assertEqual(parse_command('What is 245 times 18?'),('calculate','245 * 18'))
        self.assertIsNone(parse_command('She said open calculator yesterday'))

    def test_local_answer_skips_reply_provider_and_saves_both_messages(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            client=LiveConversation('test',groq_api_key='',reply_provider='sarvam',
                memory_path=Path(folder)/'memory.sqlite',transport=httpx.MockTransport(lambda request:self.fail('Unexpected provider call')))
            try:
                answer=client.reply(RecognizedTurn('Calculate 245 * 18','en-IN',None,False))
                self.assertIn('4410',answer)
                self.assertEqual([r['role'] for r in client.memory.recent()],['user','assistant'])
            finally: client.close()

    def test_timer_is_durable_and_fires_only_once(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            path=Path(folder)/'timers.sqlite'
            LocalTimers(path).create(5,now=100)
            timers=LocalTimers(path)
            self.assertEqual(timers.due(now=104),[])
            self.assertEqual(len(timers.due(now=105)),1)
            self.assertEqual(timers.due(now=200),[])

    def test_permissions_block_action_and_strictness_does_not_override_them(self):
        profile=CharacterProfile({'permissions':{'desktop_apps':False},'tone':'strict'})
        launch=Mock()
        with patch('src.agent_tools.CharacterProfile.load',return_value=profile):
            result=DesktopTools(launcher=launch).execute('open_app',{'app':'calculator'},'Open calculator')
        self.assertEqual(result['status'],'disabled')
        launch.assert_not_called()

    def test_controls_preserve_voice_context_and_personality_fields(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            path=Path(folder)/'profile.json'
            original={'name':'Amma','role':'mother','custom_instructions':'Be direct.',
                'context':{'file_search_roots':['D:/example']},'speech_delivery':{'pace':1.18,'enable_qc':False}}
            path.write_text(json.dumps(original),encoding='utf-8')
            permissions={key:True for key in CharacterProfile.CAPABILITIES}; permissions['internet']=False
            profile=CharacterProfile.save_controls(permissions,'strict',path,pace=1.2)
            self.assertEqual(profile.data['context'],original['context'])
            self.assertEqual(profile.data['custom_instructions'],'Be direct.')
            self.assertFalse(profile.allowed('internet'))
            self.assertEqual(profile.data['speech_delivery']['pace'],1.2)
            self.assertFalse(profile.data['speech_delivery']['enable_qc'])
