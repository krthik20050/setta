import unittest
from src.manglish import to_manglish


class ManglishTests(unittest.TestCase):
    def test_no_malayalam_glyph_can_escape_into_a_bubble(self):
        output = to_manglish(''.join(chr(n) for n in range(0x0D00, 0x0D80)))
        self.assertFalse(any('\u0d00' <= c <= '\u0d7f' for c in output))

    def test_greeting(self):
        self.assertEqual(to_manglish('അമ്മ മോനേ സുഖമാണോ?'), 'amma mone sukhamaano?')

    def test_mixed_english(self):
        self.assertEqual(to_manglish('മോനേ, lunch ready!'), 'mone, lunch ready!')

    def test_chillu_and_conjunct(self):
        self.assertEqual(to_manglish('എന്താ അവൻ'), 'enthaa avan')
        self.assertEqual(to_manglish('അവന്‍'), 'avan')

    def test_speech_source_unchanged(self):
        spoken = 'എന്താ മോനേ, സുഖമാണോ?'
        displayed = to_manglish(spoken)
        self.assertFalse(any('\u0d00' <= c <= '\u0d7f' for c in displayed))
        self.assertEqual(spoken, 'എന്താ മോനേ, സുഖമാണോ?')

    def test_english_unchanged(self):
        self.assertEqual(to_manglish('Hello, Karthik!'), 'Hello, Karthik!')
