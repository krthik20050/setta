from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
import json
import httpx

from src.local_actions import calculate,is_affirmative,is_negative,parse_command
from src.local_timers import LocalTimers
from src.character_profile import CharacterProfile
from src.live_conversation import LiveConversation
from src.live_conversation import app_category_request
from src.sarvam_conversation import RecognizedTurn
from src.agent_tools import DesktopTools
from src.companion_context import Observation


class LocalActionsProfileTests(unittest.TestCase):
    def test_category_request_parser_requires_launch_intent(self):
        self.assertEqual(app_category_request('Could you open a design app?'),'design')
        self.assertEqual(app_category_request('Launch my browser'),'browser')
        self.assertEqual(app_category_request('open design apps'),'design')
        self.assertEqual(app_category_request('design apps'),'design')
        self.assertIsNone(app_category_request('I use a design app every day'))
        self.assertEqual(app_category_request('open creative apps'),'design')

    def test_short_confirmation_language_is_explicit_and_bounded(self):
        for phrase in ('yes', 'Yes please!', 'go ahead', 'sure'):
            self.assertTrue(is_affirmative(phrase))
        for phrase in ('no', 'cancel', 'never mind'):
            self.assertTrue(is_negative(phrase))
        self.assertFalse(is_affirmative('yes, open Figma and share my screen'))

    def test_parse_command_accepts_discovered_app_names(self):
        self.assertEqual(parse_command('Open Figma', {'figma', 'file_explorer'}), ('open_app', 'figma'))
        self.assertEqual(parse_command('docker desktop', {'docker_desktop'}), ('open_app', 'docker_desktop'))
        self.assertEqual(parse_command('Please launch the file explorer', {'figma', 'file_explorer'}),
                         ('open_app', 'file_explorer'))
        self.assertEqual(parse_command('Open Figma', {'figma'}), ('open_app', 'figma'))
        for phrase in ('Could you open Figma app?', 'Please bring up Figma', 'Launch Figma now',
                       'Would you show me Figma', 'Amma, open Figma for me'):
            self.assertEqual(parse_command(phrase, {'figma'}), ('open_app', 'figma'), phrase)
        self.assertEqual(parse_command('Start browser', {'browser'}), ('open_app', 'browser'))
        self.assertEqual(parse_command('can u open like docker', {'docker_desktop'}), ('open_app', 'docker_desktop'))
        self.assertEqual(parse_command('could u open antigravity', {'antigravity'}), ('open_app','antigravity'))
        self.assertEqual(parse_command('open photoshop', {'adobe_photoshop_2025','photoshop_elements'}),
                         ('choose_app',('adobe_photoshop_2025','photoshop_elements')))
        self.assertEqual(parse_command('open photoshop', {'adobe_photoshop_2025'}),
                         ('open_app','adobe_photoshop_2025'))
        self.assertEqual(parse_command('open an app to design with', {'figma'}), None)
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

    def test_explicit_app_request_opens_immediately_and_bare_yes_does_not_repeat(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            client=LiveConversation('test',memory_path=Path(folder)/'memory.sqlite',transport=httpx.MockTransport(lambda r:httpx.Response(500)))
            self.addCleanup(client.close)
            client.profile=CharacterProfile({'permissions':{'desktop_apps':True,'camera':True}})
            client.agent_tools.launcher=Mock()
            client.agent_tools.apps['figma']=Path('C:/Program Files/Figma/Figma.exe')
            with patch.object(client.agent_tools,'_launch_target') as opened:
                answer=client.reply(RecognizedTurn('Open Figma','en-IN',None,False))
                self.assertIn('opening figma',answer.lower())
                opened.assert_called_once_with(client.agent_tools.apps['figma'])
                no_pending=client.reply(RecognizedTurn('yes','en-IN',None,False))
                self.assertIn('pending action to confirm',no_pending.lower())
                opened.assert_called_once()
            self.assertIsNone(client._pending_local_action)

    def test_app_execution_rechecks_permission_after_request(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            client=LiveConversation('test',memory_path=Path(folder)/'memory.sqlite',transport=httpx.MockTransport(lambda r:httpx.Response(500)))
            self.addCleanup(client.close)
            client.profile=CharacterProfile({'permissions':{'desktop_apps':True,'camera':True}})
            client.agent_tools.apps['figma']=Path('C:/Program Files/Figma/Figma.exe')
            permissions={key:True for key in CharacterProfile.CAPABILITIES}; permissions['desktop_apps']=False
            client.profile=CharacterProfile.save_controls(permissions,'calm',Path(folder)/'profile.json')
            with patch('src.agent_tools.CharacterProfile.load',return_value=client.profile):
                with patch.object(client.agent_tools,'_launch_target') as opened:
                    answer=client.agent_tools.execute('open_app',{'app':'figma'},'Open Figma')
            self.assertEqual(answer.get('status'),'disabled')
            opened.assert_not_called()

    def test_category_request_opens_best_installed_app_without_followup_question(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            client=LiveConversation('test',memory_path=Path(folder)/'memory.sqlite',transport=httpx.MockTransport(lambda r:self.fail('Category routing should be local')))
            self.addCleanup(client.close)
            client.profile=CharacterProfile({'permissions':{'desktop_apps':True,'camera':True}})
            client.agent_tools.apps={'figma':Path('C:/Apps/Figma.exe'),'canva':Path('C:/Apps/Canva.exe')}
            client.agent_tools.app_displays={'figma':'Figma','canva':'Canva'}
            client.agent_tools.app_usage_path=Path(folder)/'usage.json'
            with patch.object(client.agent_tools,'_launch_target') as launch:
                answer=client.reply(RecognizedTurn('Open a design app','en-IN',None,False))
                self.assertIn('Opening Figma',answer)
                launch.assert_called_once_with(Path('C:/Apps/Figma.exe'))

    def test_explicit_docker_ellipsis_and_bare_choice_open_without_provider(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            client=LiveConversation('test',memory_path=Path(folder)/'memory.sqlite',
                transport=httpx.MockTransport(lambda r:self.fail('Explicit app request must stay local')))
            self.addCleanup(client.close)
            client.profile=CharacterProfile({'permissions':{'desktop_apps':True,'camera':True}})
            client.agent_tools.apps={'docker_desktop':Path('C:/Apps/Docker Desktop.exe')}
            client.agent_tools.app_displays={'docker_desktop':'Docker Desktop'}
            with patch.object(client.agent_tools,'_launch_target') as launch:
                answer=client.reply(RecognizedTurn('can u open like docker','en-IN',None,False))
            self.assertIn('Docker Desktop',answer)
            launch.assert_called_once_with(Path('C:/Apps/Docker Desktop.exe'))

    def test_could_u_open_antigravity_launches_without_confirmation(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            client=LiveConversation('test',memory_path=Path(folder)/'memory.sqlite',
                transport=httpx.MockTransport(lambda r:self.fail('Antigravity intent should stay local')))
            self.addCleanup(client.close)
            client.profile=CharacterProfile({'permissions':{'desktop_apps':True,'camera':True}})
            client.agent_tools.apps={'antigravity':Path('C:/Apps/Antigravity.exe')}
            client.agent_tools.app_displays={'antigravity':'Antigravity'}
            with patch.object(client.agent_tools,'_launch_target') as launch:
                answer=client.reply(RecognizedTurn('i was thinking of working could u open antigravity','en-IN',None,False))
            self.assertIn('Antigravity',answer)
            self.assertNotIn('should I',answer.lower())
            launch.assert_called_once_with(Path('C:/Apps/Antigravity.exe'))

    def test_app_executor_accepts_authorized_ellipsis_without_request_rewrite(self):
        profile=CharacterProfile({'permissions':{'desktop_apps':True}})
        tools=DesktopTools(launcher=Mock())
        tools.apps={'docker_desktop':Path('C:/Apps/Docker Desktop.exe')}
        tools.app_displays={'docker_desktop':'Docker Desktop'}
        with patch('src.agent_tools.CharacterProfile.load',return_value=profile):
            with patch.object(tools,'_launch_target') as launch:
                result=tools.execute('open_app',{'app':'docker_desktop'},'can u open like docker')
        self.assertEqual(result['status'],'launch_requested')
        launch.assert_called_once_with(Path('C:/Apps/Docker Desktop.exe'))

    def test_bare_app_name_launches_and_plural_category_stays_local(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            client=LiveConversation('test',memory_path=Path(folder)/'memory.sqlite',
                transport=httpx.MockTransport(lambda r:self.fail('App intent should not call provider')))
            self.addCleanup(client.close)
            client.profile=CharacterProfile({'permissions':{'desktop_apps':True,'camera':True,'desktop_context':False}})
            client.agent_tools.apps={'docker_desktop':Path('C:/Apps/Docker Desktop.exe'),
                'figma':Path('C:/Apps/Figma.exe'),'photoshop':Path('C:/Apps/Photoshop.exe')}
            client.agent_tools.app_displays={'docker_desktop':'Docker Desktop','figma':'Figma','photoshop':'Photoshop'}
            client.agent_tools.app_usage_path=Path(folder)/'usage.json'
            with patch.object(client.agent_tools,'_launch_target') as launch:
                opened=client.reply(RecognizedTurn('Docker Desktop','en-IN',None,False))
                self.assertIn('Opening Docker Desktop',opened)
                launch.assert_called_once_with(Path('C:/Apps/Docker Desktop.exe'))
                opened_design=client.reply(RecognizedTurn('design apps','en-IN',None,False))
                self.assertIn('Opening',opened_design)
                self.assertEqual(launch.call_count,2)

    def test_usual_category_app_uses_permissioned_foreground_history(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            client=LiveConversation('test',memory_path=Path(folder)/'memory.sqlite',
                transport=httpx.MockTransport(lambda r:self.fail('Usual app resolution must remain local')))
            self.addCleanup(client.close)
            client.profile=CharacterProfile({'permissions':{'desktop_apps':True,'camera':True,'desktop_context':True}})
            client.agent_tools.apps={'figma':Path('C:/Apps/Figma.exe'),'canva':Path('C:/Apps/Canva.exe')}
            client.agent_tools.app_displays={'figma':'Figma','canva':'Canva'}
            client.agent_tools.app_usage_path=Path(folder)/'usage.json'
            client.observations=lambda:[Observation(
                'recent_desktop_activity',json.dumps([{'app':'Figma.exe'},{'app':'Figma.exe'}]),
                'test',1.0,0.0)]
            with patch.object(client.agent_tools,'_launch_target') as launch:
                answer=client.reply(RecognizedTurn('open my usual design app','en-IN',None,False))
            self.assertIn('Figma',answer)
            launch.assert_called_once_with(Path('C:/Apps/Figma.exe'))


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
