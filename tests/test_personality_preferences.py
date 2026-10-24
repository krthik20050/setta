import unittest

from src.personality_preferences import parse_personality_correction


class PersonalityPreferenceParserTests(unittest.TestCase):
    def test_recognizes_one_off_and_explicit_durable_changes(self):
        one_off = parse_personality_correction('Could you be shorter?')
        self.assertEqual(one_off.values, {'reply_length': 'brief'})
        self.assertFalse(one_off.persistent)
        self.assertTrue(one_off.command_only)

        durable = parse_personality_correction('From now on, keep it brief.')
        self.assertEqual(durable.values, {'reply_length': 'brief'})
        self.assertTrue(durable.persistent)

    def test_recognizes_conversation_behaviors(self):
        self.assertEqual(parse_personality_correction("Don't give me advice unless I ask").values,
                         {'advice_style': 'ask_first'})
        self.assertEqual(parse_personality_correction('Please ask fewer follow-up questions').values,
                         {'follow_up': 'only_when_needed'})
        self.assertEqual(parse_personality_correction('No jokes please').values, {'humor': 'off'})

    def test_supports_the_companions_spoken_languages(self):
        self.assertEqual(parse_personality_correction('अब से संक्षेप में बताओ').values,
                         {'reply_length': 'brief'})
        self.assertTrue(parse_personality_correction('अब से संक्षेप में बताओ').persistent)
        self.assertEqual(parse_personality_correction('ഇനി മുതൽ ചുരുക്കി പറയൂ').values,
                         {'reply_length': 'brief'})
        self.assertTrue(parse_personality_correction('ഇനി മുതൽ ചുരുക്കി പറയൂ').persistent)

    def test_separates_embedded_request_from_preference_command(self):
        value = parse_personality_correction('Explain this briefly: photosynthesis')
        self.assertEqual(value.values, {'reply_length': 'brief'})
        self.assertFalse(value.command_only)

    def test_unrelated_mentions_and_conflicting_intents_do_not_match(self):
        self.assertIsNone(parse_personality_correction('I prefer short walks and detailed books.'))
        self.assertIsNone(parse_personality_correction('Be brief but give longer answers'))


if __name__ == '__main__':
    unittest.main()
