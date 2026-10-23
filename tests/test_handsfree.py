import base64
import threading
import unittest
from unittest.mock import MagicMock,patch
import httpx
from src.handsfree_server import HandsfreeServer
from src.sarvam_conversation import RecognizedTurn,SarvamConversation


class HandsfreeTests(unittest.TestCase):
    def test_streaming_clone_contract_omits_non_stream_fields(self):
        def handle(request):
            self.assertEqual(request.url.path,'/voices/clone/stream')
            self.assertIn(b'linear16',request.content)
            self.assertNotIn(b'enable_qc',request.content)
            self.assertNotIn(b'enable_vad',request.content)
            return httpx.Response(200,content=b'\0\0'*4800)
        client=SarvamConversation('test',openai_api_key='',groq_api_key='',reply_provider='sarvam',transport=httpx.MockTransport(handle))
        self.addCleanup(client.close)
        self.assertEqual(sum(len(c) for c in client.stream_speech('Hello',RecognizedTurn('Hello','en-IN',None,False))),9600)

    def test_loopback_endpoint_rejects_foreign_origin_and_requires_token(self):
        conversation=MagicMock()
        with patch('src.handsfree_server.LiveConversation',return_value=conversation):
            server=HandsfreeServer('test',port=0)
        server.start()
        try:
            with httpx.Client(base_url=server.origin) as client:
                self.assertEqual(client.get('/').status_code,200)
                self.assertEqual(client.post('/cancel',json={}).status_code,403)
                self.assertEqual(client.post('/cancel',json={},headers={'Origin':'https://evil.test','X-Amma-Token':server.token}).status_code,403)
                self.assertEqual(client.post('/cancel',json={},headers={'Origin':server.origin,'X-Amma-Token':server.token}).status_code,204)
        finally: server.stop()

    def test_new_utterance_cancels_stream_and_unheard_reply_is_removed(self):
        conversation=MagicMock()
        conversation.recognize.return_value=RecognizedTurn('Hello','en-IN',None,False)
        conversation.reply.return_value='Hello there.'
        conversation.memory.recent.return_value=[{'id':19,'role':'assistant'}]
        conversation.stream_speech.return_value=iter([b'\0\0'*2400,b'\0\0'*2400])
        with patch('src.handsfree_server.LiveConversation',return_value=conversation):
            server=HandsfreeServer('test',port=0)
        server.start(); events=[]; ticket=server.invalidate()
        def emit(event):
            events.append(event)
            if event['type']=='audio': server.invalidate()
        try:
            server.process(b'fake-wave',ticket,emit)
            self.assertEqual([e['type'] for e in events],['transcript','reply','audio'])
            conversation.memory.delete_message.assert_called_once_with(19)
        finally: server.stop()
