import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import httpx

from src.agent_tools import DesktopTools
from src.character_profile import CharacterProfile
from src.sarvam_conversation import SarvamConversation,RecognizedTurn


class AgentToolTests(unittest.TestCase):
    def test_search_browser_opens_default_browser_and_returns_search_result(self):
        tools=DesktopTools(launcher=Mock())
        tools.web.execute=Mock(return_value={'status':'ok','digest':'Verified result'})
        with patch('src.agent_tools.webbrowser.open') as opened:
            result=tools.execute('search_browser',{'query':'Figma'},'Please search for Figma')
        opened.assert_called_once()
        self.assertIn('google.com/search', opened.call_args.args[0])
        self.assertEqual(result['digest'],'Verified result')
        self.assertTrue(result['browser_opened'])

    def test_search_is_bounded_to_roots_and_does_not_return_environment_files(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            root=Path(folder); (root/'readme.md').write_text('sample'); (root/'.env').write_text('private')
            tools=DesktopTools(roots=[root],launcher=Mock())
            self.assertEqual(tools.execute('find_files',{'pattern':'../*'},'Find files')['status'],'unavailable')
            # Runtime is deliberately excluded in production; use a temporary
            # ordinary project folder for the allowlist contract below.
            self.assertFalse(tools._safe(root/'.env'))

    def test_opening_requires_a_real_user_action_request(self):
        launcher=Mock(); tools=DesktopTools(launcher=launcher)
        self.assertEqual(tools.execute('open_app',{'app':'notepad'},'Which apps are open?')['status'],'unavailable')
        launcher.assert_not_called()
        result=tools.execute('open_app',{'app':'notepad'},'Please open Notepad')
        self.assertEqual(result['status'],'launch_requested'); self.assertFalse(result['verified_open'])
        launcher.assert_called_once()
        tools.cancelled=lambda:True
        self.assertEqual(tools.execute('open_app',{'app':'calculator'},'Open calculator')['status'],'cancelled')
        launcher.assert_called_once()
        tools.cancelled=lambda:False
        self.assertEqual(tools.execute('open_file',{'path':'C:/Windows/System32/cmd.exe'},'Open cmd')['status'],'unavailable')

    def test_model_cannot_choose_an_arbitrary_app_for_ambiguous_category_request(self):
        profile=CharacterProfile({'permissions':{'desktop_apps':True}})
        tools=DesktopTools(launcher=Mock())
        tools.apps={'figma':Path('C:/Apps/Figma.exe')}
        with patch('src.agent_tools.CharacterProfile.load',return_value=profile):
            with patch.object(tools,'_launch_target') as launch:
                result=tools.execute('open_app',{'app':'figma'},'Could you open a design app?')
        self.assertEqual(result['status'],'unavailable')
        launch.assert_not_called()

    def test_resolved_category_candidate_still_uses_permission_checked_launcher(self):
        profile=CharacterProfile({'permissions':{'desktop_apps':True}})
        tools=DesktopTools(launcher=Mock())
        tools.apps={'figma':Path('C:/Apps/Figma.exe')}
        with patch('src.agent_tools.CharacterProfile.load',return_value=profile):
            with patch.object(tools,'_launch_target') as launch:
                result=tools.execute_resolved_app('figma','Could you open a design app?')
        self.assertEqual(result['status'],'launch_requested')
        launch.assert_called_once_with(Path('C:/Apps/Figma.exe'))

    def test_catalog_style_app_target_can_be_launched(self):
        launcher=Mock()
        tools=DesktopTools(launcher=launcher)
        tools.apps['docker_desktop']=Path(r'C:\Program Files\Docker\Docker\Docker Desktop.exe')
        with patch.object(tools, '_launch_target') as launch:
            result=tools.execute('open_app',{'app':'docker_desktop'},'Please open Docker Desktop')
        launch.assert_called_once()
        self.assertEqual(result['status'],'launch_requested')

    def test_app_candidates_do_not_treat_launch_requests_as_observed_usage(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            tools=DesktopTools(launcher=Mock())
            tools.app_usage_path=Path(folder)/'usage.json'
            tools.apps={'figma':Path('C:/Apps/Figma.exe'),'canva':Path('C:/Apps/Canva.exe'),
                        'notepad':Path('C:/Windows/notepad.exe')}
            tools.app_displays={'figma':'Figma','canva':'Canva','notepad':'Notepad'}
            candidates=tools.app_candidates('design')
            self.assertEqual({row['app'] for row in candidates},{'canva','figma'})
            observed=tools.app_candidates('design',observed_apps=['Canva.exe'])
            self.assertEqual(observed[0]['app'],'canva')

    def test_app_candidates_ignore_launch_requests_and_rank_observed_foreground_use(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            tools=DesktopTools(launcher=Mock())
            tools.app_usage_path=Path(folder)/'usage.json'
            tools.apps={'figma':Path('C:/Apps/Figma.exe'),'canva':Path('C:/Apps/Canva.exe')}
            tools.app_displays={'figma':'Figma','canva':'Canva'}
            tools.app_usage_path.write_text(json.dumps({'figma':{'launch_requests':100,'last_launch_request':9999999999}}),encoding='utf-8')
            candidates=tools.app_candidates('design')
            scores={row['app']:row['score'] for row in candidates}
            self.assertEqual(scores['figma'],scores['canva'])
            observed=tools.app_candidates('design',observed_apps=['Canva.exe'])
            self.assertGreater(observed[0]['score'],next(row['score'] for row in observed if row['app']=='figma'))

    def test_category_candidates_do_not_match_target_path_or_settings_substrings(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            tools=DesktopTools(launcher=Mock())
            tools.app_usage_path=Path(folder)/'usage.json'
            tools.apps={'figma':'com.squirrel.Figma.Figma','network_internet':'ms-settings:network',
                        'restartagent':'C:/Apps/restartagent.exe','illustrator':'illustrator'}
            tools.app_displays={'figma':'Figma','network_internet':'Network & Internet',
                                'restartagent':'restartagent','illustrator':'Adobe Illustrator 2025'}
            self.assertEqual({row['app'] for row in tools.app_candidates('browser')},set())
            self.assertEqual({row['app'] for row in tools.app_candidates('design')},{'figma','illustrator'})

    def test_foreground_executable_history_matches_installed_display_name(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            tools=DesktopTools(launcher=Mock())
            tools.app_usage_path=Path(folder)/'usage.json'
            tools.apps={'figma':'com.squirrel.Figma.Figma','chrome':'Chrome',
                        'google_chrome':'C:/Program Files/Chrome/chrome.exe'}
            tools.app_displays={'figma':'Figma','chrome':'Chrome','google_chrome':'Google Chrome'}
            rows=tools.app_candidates('design',observed_apps=['Figma.exe'])
            self.assertEqual(rows[0]['observed_history_matches'],1)
            browsers=tools.app_candidates('browser')
            self.assertEqual(sum(row['display_name'] in {'Chrome','Google Chrome'} for row in browsers),1)

    def test_real_odd_cache_is_discovered_across_sandbox_localappdata(self):
        with patch.dict('os.environ',{'LOCALAPPDATA':r'C:\Users\DELL\AppData\Local\Packages\sandbox\AC',
                                     'USERPROFILE':r'C:\Users\DELL'}):
            tools=DesktopTools(launcher=Mock())
        self.assertTrue(tools.app_cache_path.name=='apps_cache.json')
        self.assertIn('figma',tools.apps)
        self.assertEqual(tools.app_displays['figma'],'Figma')

    def test_search_returns_real_filename_without_reading_its_contents(self):
        root=Path(__file__).resolve().parents[1]
        tools=DesktopTools(roots=[root],launcher=Mock())
        result=tools.execute('find_files',{'pattern':'face-correction-v10.md'},'Find the face correction document')
        self.assertIn(str(root/'docs/companion/face-correction-v10.md'),result['files'])
        self.assertNotIn('contents',result)

    def test_groq_tool_loop_uses_actual_result_and_deduplicates_same_action(self):
        execute=Mock(return_value={'status':'launch_requested','verified_open':False})
        tools=Mock(schemas=[{'type':'function','function':{'name':'open_app','parameters':{'type':'object'}}}],execute=execute)
        calls=[]
        def handle(request):
            body=json.loads(request.content); calls.append(body)
            if len(calls)<3:
                return httpx.Response(200,json={'choices':[{'finish_reason':'tool_calls','message':{
                    'role':'assistant','tool_calls':[{'id':'call'+str(len(calls)),'type':'function',
                    'function':{'name':'open_app','arguments':'{"app":"notepad"}'}}]}}]})
            self.assertIn('launch_requested',json.dumps(body['messages']))
            return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':'I requested Notepad to open.'}}]})
        client=SarvamConversation('test',openai_api_key='',groq_api_key='test',reply_provider='groq',transport=httpx.MockTransport(handle))
        self.addCleanup(client.close); client.agent_tools=tools
        self.assertEqual(client.reply(RecognizedTurn('Open Notepad','en-IN',None,False)),'I requested Notepad to open.')
        execute.assert_called_once()
