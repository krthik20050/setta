import unittest

from src.skill_registry import DEFAULT_SKILLS, SkillRegistry, SkillSpec


class SkillRegistryTests(unittest.TestCase):
    def test_default_skills_are_bounded_and_selectable(self):
        skill = DEFAULT_SKILLS.for_intent('play_media')[0]
        self.assertEqual(skill.name, 'play-youtube-media')
        self.assertLessEqual(skill.max_steps, 32)
        self.assertIn('desktop_apps', skill.permissions)
        self.assertIn('play_youtube_music', skill.tools)

    def test_duplicate_and_invalid_skills_fail_closed(self):
        skill = SkillSpec('demo', 'Demo', ('demo',), ('tool',), ())
        registry = SkillRegistry((skill,))
        with self.assertRaises(ValueError):
            registry.register(skill)
        with self.assertRaises(ValueError):
            SkillSpec('bad', 'Bad', ('bad',), ('tool',), (), max_steps=0)


if __name__ == '__main__':
    unittest.main()
