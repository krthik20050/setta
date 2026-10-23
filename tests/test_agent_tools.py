import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import httpx

from src.agent_tools import DesktopTools
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

    def test_catalog_style_app_target_can_be_launched(self):
        launcher=Mock()
        tools=DesktopTools(launcher=launcher)
        tools.apps['docker_desktop']=Path(r'C:\Program Files\Docker\Docker\Docker Desktop.exe')
        with patch.object(tools, '_launch_target') as launch:
            result=tools.execute('open_app',{'app':'docker_desktop'},'Please open Docker Desktop')
        launch.assert_called_once()
        self.assertEqual(result['status'],'launch_requested')

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
