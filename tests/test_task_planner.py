import unittest

from src.task_planner import plan_request, select_media_service


class TaskPlannerTests(unittest.TestCase):
    def test_plans_natural_youtube_music_request(self):
        plan = plan_request('Open Brave and play some relaxing music on YouTube')
        self.assertIsNotNone(plan)
        self.assertEqual(plan.steps[0].arguments['query'], 'relaxing music')

    def test_ignores_unrelated_mentions(self):
        self.assertIsNone(plan_request('I like music and YouTube'))

    def test_generic_music_prefers_spotify_and_youtube_stays_explicit(self):
        spotify = plan_request('Play some relaxing music', {'spotify', 'brave'})
        youtube = plan_request('Play relaxing music on YouTube', {'spotify', 'brave'})
        self.assertEqual(spotify.steps[0].tool, 'play_spotify_music')
        self.assertEqual(youtube.steps[0].tool, 'play_youtube_music')

    def test_service_selection_uses_explicit_request_then_availability(self):
        self.assertEqual(select_media_service('Play a music video', {'spotify', 'brave'}), 'youtube')
        self.assertEqual(select_media_service('Play it on Spotify', {'spotify', 'brave'}), 'spotify')
        self.assertEqual(select_media_service('Play music', {'brave'}), 'youtube')
        self.assertIsNone(select_media_service('Play music', {'notepad'}))


if __name__ == '__main__':
    unittest.main()
