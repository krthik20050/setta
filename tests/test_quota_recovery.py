import os
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from src.reply_fallback import ReplyFallback
from src.character_profile import CharacterProfile
from src.companion_context import CompanionContext


class QuotaRecoveryTests(unittest.TestCase):
    def test_shared_cooldown_routes_second_session_to_independent_sarvam(self):
        seen=[]
        def handle(request):
            payload=json.loads(request.content)
            seen.append(request.url.host)
            if request.url.host=='api.groq.com':
                return httpx.Response(429,headers={'retry-after':'20'})
            self.assertEqual(request.url.host,'api.sarvam.ai')
            self.assertNotIn('authorization',request.headers)
            self.assertEqual(request.headers['api-subscription-key'],'sarvam-test')
            self.assertEqual(payload['messages'][0]['role'],'tool')
            self.assertEqual(payload['max_tokens'],350)
            self.assertNotIn('max_completion_tokens',payload)
            return httpx.Response(200,json={'choices':[{'message':{'content':'Okay.'}}]})
        with patch.dict(os.environ,{'SARVAM_REPLY_FALLBACK':'1','OMNIROUTE_MODEL':'','OMNIROUTE_API_KEY':''}), \
             tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder, \
             patch('src.reply_fallback.RUNTIME_DIR',Path(folder)):
            transport=httpx.MockTransport(handle)
            routers=[ReplyFallback(transport,sarvam_key='sarvam-test') for _ in range(2)]
            try:
                with httpx.Client(base_url='https://api.groq.com',headers={'Authorization':'Bearer shared-quota-test'},transport=transport) as primary:
                    payload={'model':'quota-test-model','messages':[{'role':'tool','tool_call_id':'one','content':'result'}],
                        'max_completion_tokens':768,'reasoning_effort':'low'}
                    for router in routers: self.assertEqual(router.post(primary,payload).status_code,200)
                self.assertEqual(seen,['api.groq.com','api.sarvam.ai','api.sarvam.ai'])
                log=(Path(folder)/'reply-usage.jsonl').read_text()
                self.assertNotIn('sarvam-test',log)
                self.assertNotIn('tool_call_id',log)
            finally:
                for router in routers: router.close()

    def test_compact_prompt_preserves_identity_and_owner_instructions(self):
        profile=CharacterProfile({'name':'Amma','confirmed_facts':{'owner':'Karthik'},
            'custom_instructions':'Use restrained warmth.'})
        brief=profile.reply_instructions('ml-IN')
        self.assertIn('mone',brief)
        self.assertIn('Karthik',brief)
        self.assertIn('Use restrained warmth.',brief)
        self.assertLess(len(brief),len(profile.instructions('ml-IN')))

    def test_compact_memory_does_not_mutate_or_delete_saved_facts(self):
        facts=[{'key':'note'+str(i),'value':'v'*900,'source_message_id':i} for i in range(10)]
        facts.append({'key':'user_name','value':'Karthik','source_message_id':99})
        bundle={'confirmed_facts':facts,'recent':[]}
        message=CompanionContext.context_message(bundle,compact=True)['content']
        self.assertIn('Karthik',message)
        self.assertIn('omitted_fact_count',message)
        self.assertEqual(len(bundle['confirmed_facts']),11)
