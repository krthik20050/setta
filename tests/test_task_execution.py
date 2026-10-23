import unittest

from src.skill_registry import DEFAULT_SKILLS
from src.task_execution import TaskExecutor, TaskPlan, TaskStep


class TaskExecutionTests(unittest.TestCase):
    def test_plan_executes_steps_and_requires_verification(self):
        calls = []

        def execute(tool, arguments):
            calls.append((tool, arguments))
            return {'status': 'ok'}

        skill = DEFAULT_SKILLS.get('play-youtube-media')
        plan = TaskPlan(skill, (
            TaskStep('open', 'open_app', {'app': 'brave'}),
            TaskStep('navigate', 'browser_navigate', {'url': 'https://youtube.com'}),
        ))
        result = TaskExecutor(DEFAULT_SKILLS, execute, lambda _: True).run(plan)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(calls), 2)

    def test_failed_postcondition_stops_before_later_steps(self):
        calls = []
        skill = DEFAULT_SKILLS.get('play-youtube-media')
        plan = TaskPlan(skill, (
            TaskStep('open', 'open_app', verifier=lambda result: result.get('verified_open', False)),
            TaskStep('never', 'browser_navigate'),
        ))
        result = TaskExecutor(
            DEFAULT_SKILLS,
            lambda tool, args: calls.append(tool) or {'status': 'launch_requested', 'verified_open': False},
            lambda _: True,
        ).run(plan)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(calls, ['open_app'])

    def test_permission_and_cancellation_fail_closed(self):
        skill = DEFAULT_SKILLS.get('play-youtube-media')
        plan = TaskPlan(skill, (TaskStep('open', 'open_app'),))
        disabled = TaskExecutor(DEFAULT_SKILLS, lambda *_: {}, lambda _: False).run(plan)
        self.assertEqual(disabled['status'], 'disabled')
        cancelled = TaskExecutor(DEFAULT_SKILLS, lambda *_: {}, lambda _: True, lambda: True).run(plan)
        self.assertEqual(cancelled['status'], 'cancelled')


if __name__ == '__main__':
    unittest.main()
