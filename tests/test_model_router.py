import unittest

from src.model_router import choose_tier


class ModelRouterTests(unittest.TestCase):
    def assertTier(self, text, tier, language='en-IN'):
        self.assertEqual(choose_tier(text, language).tier, tier, text)

    def test_small_talk_and_feelings_stay_fast(self):
        for text in ['Hi Amma', 'How are you?', 'I am so tired today', 'I got the job!',
                     'Play some music', 'What is the weather in Kochi?', 'Thank you']:
            self.assertTier(text, 'fast')

    def test_reasoning_requests_go_deep(self):
        for text in ['Plan my study week for the physics exam',
                     'Compare Python and JavaScript for a beginner',
                     'Explain why the sky is blue',
                     'How does a vaccine work?',
                     'What are the pros and cons of renting?',
                     'Research the best laptops under 60000',
                     'Help me write an email to my professor about an extension',
                     'Walk me through this step by step',
                     'Should I take the job offer or stay?']:
            self.assertTier(text, 'deep')

    def test_long_or_multi_part_requests_go_deep(self):
        long_text = ' '.join(['word'] * 35)
        route = choose_tier(long_text, 'en-IN')
        self.assertEqual((route.tier, route.reason), ('deep', 'long_request'))
        route = choose_tier('What is RAM? And what does a GPU do?', 'en-IN')
        self.assertEqual((route.tier, route.reason), ('deep', 'multi_part'))

    def test_hindi_and_malayalam_reasoning_cues(self):
        self.assertTier('आसमान नीला क्यों है', 'deep', 'hi-IN')
        self.assertTier('इन दोनों की तुलना करो', 'deep', 'hi-IN')
        self.assertTier('ആകാശം എന്തുകൊണ്ട് നീലയാണ്', 'deep', 'ml-IN')
        self.assertTier('ഇത് വിശദീകരിക്കാമോ', 'deep', 'ml-IN')

    def test_native_greetings_stay_fast(self):
        self.assertTier('आप कैसे हो', 'fast', 'hi-IN')
        self.assertTier('സുഖമാണോ അമ്മേ', 'fast', 'ml-IN')
        self.assertTier('എങ്ങനെയുണ്ട്', 'fast', 'ml-IN')

    def test_reason_is_reported(self):
        self.assertEqual(choose_tier('Compare these two phones', 'en-IN').reason, 'reasoning_keyword')
        self.assertEqual(choose_tier('Hello', 'en-IN').reason, 'default')


if __name__ == '__main__':
    unittest.main()
