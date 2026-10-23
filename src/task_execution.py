"""Bounded plan execution for approved skills.

This layer coordinates tools but does not decide permissions. A caller must
provide an authorization callback backed by Profile & Memory permissions.
"""
from dataclasses import dataclass, field
from typing import Callable, Mapping

from .skill_registry import SkillRegistry, SkillSpec


@dataclass(frozen=True)
class TaskStep:
    id: str
    tool: str
    arguments: Mapping[str, object] = field(default_factory=dict)
    verifier: Callable[[Mapping[str, object]], bool] | None = None


@dataclass
class TaskPlan:
    skill: SkillSpec
    steps: tuple[TaskStep, ...]

    def __post_init__(self):
        if not self.steps:
            raise ValueError('A task plan needs at least one step')
        if len(self.steps) > self.skill.max_steps:
            raise ValueError('Task plan exceeds the skill step limit')
        if len({step.id for step in self.steps}) != len(self.steps):
            raise ValueError('Task step IDs must be unique')
        unsupported = {step.tool for step in self.steps} - set(self.skill.tools)
        if unsupported:
            raise ValueError('Task plan contains tools outside the skill contract')


class TaskExecutor:
    def __init__(self, registry: SkillRegistry, execute: Callable[[str, Mapping[str, object]], Mapping[str, object]],
                 allowed: Callable[[str], bool], cancelled: Callable[[], bool] = lambda: False):
        self.registry = registry
        self.execute_tool = execute
        self.allowed = allowed
        self.cancelled = cancelled

    def run(self, plan: TaskPlan) -> dict[str, object]:
        if self.registry.get(plan.skill.name) is not plan.skill:
            return {'status': 'rejected', 'reason': 'Skill is not registered.'}
        missing = [permission for permission in plan.skill.permissions if not self.allowed(permission)]
        if missing:
            return {'status': 'disabled', 'reason': 'Missing permission: '+', '.join(missing)}
        results = []
        for step in plan.steps:
            if self.cancelled():
                return {'status': 'cancelled', 'results': results}
            result = dict(self.execute_tool(step.tool, step.arguments))
            verified = bool(step.verifier(result)) if step.verifier else result.get('status') not in {
                'disabled', 'unavailable', 'cancelled', 'failed'}
            results.append({'id': step.id, 'tool': step.tool, 'result': result, 'verified': verified})
            if not verified:
                return {'status': 'blocked', 'failed_step': step.id, 'results': results}
        return {'status': 'completed', 'results': results}
