import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace

import httpx
import numpy as np
from PIL import Image

from src.web_tools import WebTools
from src.face_id import FaceID
from src.thought_bubble import bubble_layout


class InternetTests(unittest.TestCase):
    def test_weather_uses_country_and_does_not_send_provider_credentials(self):
        def handle(request):
            self.assertNotIn('authorization',request.headers)
            if 'geocoding' in request.url.host:
                self.assertEqual(request.url.params['countryCode'],'IN')
                return httpx.Response(200,json={'results':[{'name':'Kochi','country_code':'IN',
                    'country':'India','admin1':'Kerala','latitude':10,'longitude':76}]})
            self.assertEqual(request.url.host,'api.open-meteo.com')
            return httpx.Response(200,json={'current':{'time':'2026-10-21T19:00','temperature_2m':28},
                'current_units':{'temperature_2m':'°C'},'timezone':'Asia/Kolkata'})
        result=WebTools(httpx.MockTransport(handle)).execute('get_weather',{'city':'Kochi','country_code':'IN'})
        self.assertEqual(result['current']['temperature_2m'],28)
        self.assertEqual(result['place']['country'],'India')

    def test_ambiguous_city_never_fetches_wrong_weather(self):
        calls=[]
        def handle(request):
            calls.append(request)
            return httpx.Response(200,json={'results':[
                {'name':'Kochi','country_code':'JP','admin1':'Kochi'},
                {'name':'Kochi','country_code':'IN','admin1':'Kerala'}]})
        result=WebTools(httpx.MockTransport(handle)).execute('get_weather',{'city':'Kochi'})
        self.assertEqual(result['status'],'needs_clarification')
        self.assertEqual(len(calls),1)

    def test_search_requires_browser_tool_and_hides_provider_error_body(self):
        def handle(request):
            data=json.loads(request.content)
            self.assertEqual(data['tools'],[{'type':'browser_search'}])
            self.assertEqual(len(data['messages']),2)
            return httpx.Response(429,text='sensitive-provider-body')
        with patch.dict(os.environ,{'GROQ_API_KEY':'synthetic-key'}):
            result=WebTools(httpx.MockTransport(handle)).execute('search_web',{'query':'Latest headlines'})
        self.assertEqual(result['http_status'],429)
        self.assertNotIn('sensitive-provider-body',json.dumps(result))

    def test_generated_citation_is_not_used_as_browser_evidence(self):
        def handle(request):
            return httpx.Response(200,json={'choices':[{'message':{
                'content':'A generated summary with https://invented.example/article',
                'executed_tools':[{'name':'browser.search','search_results':{'results':[
                    {'title':'Actual result','url':'https://actual.example/news'}]}}]}}]})
        with patch.dict(os.environ,{'GROQ_API_KEY':'synthetic-key'}):
            result=WebTools(httpx.MockTransport(handle)).execute('search_web',{'query':'News'})
        self.assertEqual(result['urls'],['https://actual.example/news'])
        self.assertTrue(result['browser_executed'])

    def test_search_without_execution_evidence_is_unavailable(self):
        transport=httpx.MockTransport(lambda request:httpx.Response(200,json={
            'choices':[{'message':{'content':'Trust this invented current news'}}]}))
        with patch.dict(os.environ,{'GROQ_API_KEY':'synthetic-key'}):
            result=WebTools(transport).execute('search_web',{'query':'News'})
        self.assertEqual(result['status'],'unavailable')


class FamilyTests(unittest.TestCase):
    def test_enrollment_retains_samples_and_survives_restart(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            faces=FaceID(folder,'')
            embedding=np.arange(1,17,dtype=float)
            faces.register_face('Father',embedding)
            faces.register_face('Father',embedding+.1)
            restarted=FaceID(folder,'')
            self.assertEqual(restarted.match_face(embedding),'Father')
            self.assertEqual(restarted.known_face_embeddings['Father'].shape,(2,16))
            with self.assertRaises(ValueError): faces.register_face('../escape',embedding)

    def test_near_tie_returns_unknown(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            faces=FaceID(folder,'')
            faces.register_face('Father',np.arange(1,17))
            faces.register_face('Uncle',np.arange(1,17)+.01)
            self.assertEqual(faces.match_face(np.arange(1,17)),'Unknown')

    def test_uploaded_group_photo_is_not_silently_enrolled(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            path=Path(folder)/'group.png'
            Image.new('RGB',(200,200)).save(path)
            represent=Mock(return_value=[{'embedding':[1]*16},{'embedding':[2]*16}])
            with patch.dict('sys.modules',{'deepface.DeepFace':SimpleNamespace(represent=represent)}):
                with self.assertRaises(ValueError): FaceID(folder,'').embedding_from_photo(path)
            self.assertTrue(represent.call_args.kwargs['enforce_detection'])


class GrowingBubbleTests(unittest.TestCase):
    def test_growth_is_bounded_and_pagination_preserves_all_words(self):
        short=bubble_layout('Hello',lambda s:len(s)*7)
        long_text='This is an ordinary conversation with more words. '*100
        long=bubble_layout(long_text,lambda s:len(s)*7)
        self.assertGreater(long[0],short[0])
        self.assertGreater(long[1],short[1])
        self.assertLessEqual(long[0],440)
        self.assertLessEqual(long[1],250)
        self.assertEqual(' '.join(long[2]).split(),long_text.split())
