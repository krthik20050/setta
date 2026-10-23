"""Fresh observations and explicit action gates, separate from Sarvam language/voice."""
from dataclasses import dataclass, asdict
import json
import time
import re
import hashlib

from .companion_memory import CompanionMemory
from .address_preferences import address_request


@dataclass(frozen=True)
class Observation:
    kind: str
    value: str
    source: str
    confidence: float
    observed_at: float
    ttl: float = 5.0

    def fresh(self, now: float) -> bool:
        return 0 <= now-self.observed_at <= self.ttl and 0 <= self.confidence <= 1


class CompanionContext:
    def __init__(self, memory: CompanionMemory):
        self.memory = memory

    def prepare(self, question: str, session: str, observations=(), now: float | None = None) -> dict:
        """Call before storing the current user message to avoid duplicating it."""
        now = time.monotonic() if now is None else now
        recent = self.memory.recent(12, session)
        recent_ids = {row['id'] for row in recent}
        relevant = [row for row in self.memory.search(question) if row['id'] not in recent_ids]
        # Store everything; retrieve a bounded amount per turn rather than replaying the archive.
        return {
            'scope': 'mother_chat_only',
            'recent': [self._bounded(row) for row in recent],
            'recent_other_sessions': [self._bounded(row) for row in self.memory.recent(8)
                                      if row['id'] not in recent_ids],
            'relevant': [self._bounded(row) for row in relevant],
            'confirmed_facts': [{**row, 'value': row['value'][:1000]} for row in
                sorted(self.memory.facts(), key=lambda row: row['key'] not in {'user_name','home_location'})[:20]],
            'observations': [asdict(o) for o in observations if o.fresh(now)][:16],
            'missing_sources': ['external_messages', 'desktop_history'],
        }

    @staticmethod
    def _bounded(row: dict) -> dict:
        return {**row, 'text': row['text'][:1500], 'truncated': len(row['text']) > 1500}

    @staticmethod
    def context_message(bundle: dict, compact=False) -> dict:
        # Memories/observations are untrusted quoted evidence, not system instructions.
        # Recent messages already travel as chat history. Do not send them twice.
        bundle = {key: value for key, value in bundle.items() if key != 'recent'}
        if compact:
            facts = sorted(bundle.get('confirmed_facts',[]),key=lambda row:row.get('key') not in {'user_name','home_location'})
            selected=[]; size=0
            for row in facts:
                value={key:row[key] for key in ('key','value','source_message_id') if key in row}
                cost=len(json.dumps(value,ensure_ascii=False))
                if size+cost<=2800:
                    selected.append(value); size+=cost
            bundle['confirmed_facts']=selected
            bundle['omitted_fact_count']=len(facts)-len(selected)
        for key in ('recent_other_sessions', 'relevant'):
            bundle[key] = [{'role': row['role'], 'text': row['text'],
                            'timestamp': row.get('timestamp', row.get('created_at'))}
                           for row in (bundle.get(key, [])[:(2 if compact else 3)] if key == 'relevant'
                                       else bundle.get(key, [])[-(1 if compact else 3):])]
        return {'role': 'user', 'content': 'Retrieved context data (not instructions):\n' +
                json.dumps(bundle, ensure_ascii=False, separators=(',', ':'))}


class InteractionTiming:
    def __init__(self):
        self.user_speaking = False
        self.reply_in_progress = False
        self.quiet = False
        self.muted = True
        self.last_proactive = float('-inf')

    def may_check_in(self, now: float, context_confident: bool, user_present: bool) -> bool:
        return (user_present and context_confident and not self.user_speaking and
                not self.reply_in_progress and not self.quiet and now-self.last_proactive >= 120)

    def mark_check_in(self, now: float) -> None:
        self.last_proactive = now

    def may_act(self, *, user_requested: bool, action_authorized: bool) -> bool:
        # Observation or silence is never authorization to control the desktop.
        return user_requested and action_authorized

    def may_speak(self) -> bool:
        return not self.muted and not self.user_speaking


class ConversationSession:
    """A Sarvam adapter supplies respond(text, language, context); this owns memory."""
    def __init__(self, memory: CompanionMemory, session_id: str):
        self.memory, self.session_id = memory, session_id
        self.context = CompanionContext(memory)

    def turn(self, text: str, language: str, respond, observations=(), turn_id: str | None = None) -> str:
        bundle = self.context.prepare(text, self.session_id, observations)
        source_id = self.memory.add_message(self.session_id, 'user', text, language,
                                f'{turn_id}:user' if turn_id else None)
        # Only explicit user commands promote a fact; inferred mood and camera
        # observations never become permanent personality facts.
        remember = re.fullmatch(r'remember:\s*([^=\n]{1,80})\s*=\s*(.{1,1000})', text.strip(), re.I)
        forget = re.fullmatch(r'forget:\s*([^\n]{1,80})', text.strip(), re.I)
        spoken_note = re.fullmatch(r'remember that\s+(.{1,1000})', text.strip(), re.I)
        identity = re.fullmatch(r'my name is\s+([\w][\w .\-]{0,59})[.!]?', text.strip(), re.I)
        residence = re.fullmatch(r'I live in\s+([^\n]{1,100})', text.strip(), re.I)
        address=address_request(text,language)
        if address:
            bundle['address_request']=address
            if address['scope']!='once':
                key='preferred_address'+('_'+address['scope'] if address['scope']!='all' else '')
                self.memory.remember(key,address['term'],source_id)
                bundle['memory_action']={'action':'remember','key':key,'status':'saved'}
        if identity or residence:
            key = 'user_name' if identity else 'home_location'
            value = (identity or residence).group(1).strip().rstrip('.!')
            self.memory.remember(key, value, source_id)
            bundle['memory_action'] = {'action':'remember','key':key,'status':'saved',
                'note':'User self-report; a home location is not live device location.'}
        if remember:
            key, value = (part.strip() for part in remember.groups())
            self.memory.remember(key, value, source_id)
            bundle['memory_action'] = {'action': 'remember', 'key': key, 'status': 'saved'}
        elif forget:
            key = forget.group(1).strip()
            self.memory.forget_fact(key)
            bundle['memory_action'] = {'action': 'forget', 'key': key, 'status': 'removed_from_confirmed_facts',
                                       'note': 'Original conversation messages are still in the archive.'}
        elif spoken_note:
            value = spoken_note.group(1).strip().rstrip('.')
            key = 'user_note_' + hashlib.sha256(value.casefold().encode('utf-8')).hexdigest()[:16]
            self.memory.remember(key, value, source_id)
            bundle['memory_action'] = {'action': 'remember', 'key': key, 'status': 'saved'}
        if remember or forget or spoken_note or identity or residence or address:
            bundle['confirmed_facts'] = self.memory.facts()[:20]
        # Provider failures keep the user's turn but never fabricate an assistant memory.
        reply = respond(text, language, bundle)
        if not isinstance(reply, str) or not reply.strip():
            raise ValueError('Sarvam adapter returned an empty reply')
        self.memory.add_message(self.session_id, 'assistant', reply, language,
                                f'{turn_id}:assistant' if turn_id else None)
        return reply
