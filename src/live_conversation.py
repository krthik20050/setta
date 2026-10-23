"""Memory-enabled Sarvam adapter shared by text and microphone entry points."""
from pathlib import Path
import threading
from uuid import uuid4

from .companion_context import CompanionContext, ConversationSession, Observation
from .companion_memory import CompanionMemory
from .paths import DATA_DIR
from .sarvam_conversation import RecognizedTurn, SarvamConversation
from .camera_context import asks_about_eyewear, eyewear_observation
from .desktop_activity import desktop_question
from .agent_tools import DesktopTools
from .conversation_journal import ConversationJournal
from .decision_router import decide
from .laya_shadow import LayaShadow
from .local_actions import parse_command
from .address_preferences import resolve_address
from .local_reminders import LocalReminders
from .reminder_intent import parse_reminder
from .task_planner import plan_request
from .task_execution import TaskExecutor
from .skill_registry import DEFAULT_SKILLS


class LiveConversation(SarvamConversation):
    def __init__(self, api_key: str, *, memory_path: Path | None = None,
                 session_id: str | None = None, observations=None, camera_frame=None, camera_request=None, **kwargs):
        # Speech stays on Sarvam. Explicit REPLY_PROVIDER selects the reply service.
        kwargs['openai_api_key'] = ''
        super().__init__(api_key, **kwargs)
        self.memory = CompanionMemory(memory_path or DATA_DIR/'memory'/'companion.sqlite')
        self.session = ConversationSession(self.memory, session_id or str(uuid4()))
        archive_root = memory_path.parent/'conversation-archive' if memory_path else DATA_DIR/'conversation-archive'
        self.journal = ConversationJournal(archive_root, self.session.session_id)
        self.reminders = LocalReminders(memory_path.parent/'reminders.sqlite' if memory_path else DATA_DIR/'reminders.sqlite')
        self.journal_turn = None
        self._recognized_pending = False
        self.observations = observations or (lambda: [])
        self.camera_frame = camera_frame
        self.camera_request = camera_request
        self.shared_window_observations = []
        self.agent_tools = DesktopTools(observations=self.observations,
            roots=self.profile.data.get('context',{}).get('file_search_roots'), memory=self.memory)
        self.agent_tools.audit = lambda **details: self.journal.event(self.journal_turn,'internet_lookup',**details)
        self._turn_lock = threading.Lock()
        self.decision_shadow = LayaShadow()

    def start_new_chat(self):
        with self._turn_lock:
            self.session = ConversationSession(self.memory, str(uuid4()))
            self.journal = ConversationJournal(self.journal.root, self.session.session_id)
            self.history = []
            self.journal_turn = None
            return self.session.session_id

    def close(self):
        if getattr(self, 'decision_shadow', None):
            self.decision_shadow.close()
        if getattr(self, 'agent_tools', None):
            self.agent_tools.close()
        super().close()

    def reply(self, turn: RecognizedTurn) -> str:
        if not self._recognized_pending:
            self.journal_turn = self.journal.new_turn()
        self._recognized_pending = False
        self.journal.event(self.journal_turn, 'user_text', text=turn.text, language=turn.language)
        try:
            reply = self._reply_impl(turn)
            self.journal.event(self.journal_turn, 'reply_generated', text=reply, language=turn.language,
                               note='Generated text is not proof that playback completed.')
            return reply
        except Exception as error:
            self.journal.event(self.journal_turn, 'reply_error', error_type=type(error).__name__)
            raise

    def recognize(self, audio):
        self.journal_turn = getattr(self, 'pending_capture_id', None) or self.journal.new_turn()
        self.pending_capture_id = None
        self._recognized_pending = False
        self.journal.audio(self.journal_turn, audio)
        try:
            turn = super().recognize(audio)
            self.journal.event(self.journal_turn, 'transcription', text=turn.text if turn else '',
                               language=turn.language if turn else None)
            self._recognized_pending = turn is not None
            return turn
        except Exception as error:
            self.journal.event(self.journal_turn, 'transcription_error', error_type=type(error).__name__)
            raise

    def synthesize(self, text, turn, whole_reply=''):
        try:
            audio = super().synthesize(text, turn, whole_reply)
            self.journal.audio(self.journal_turn or self.journal.new_turn(), audio, str(uuid4())+'-reply.wav')
            return audio
        except Exception as error:
            self.journal.event(self.journal_turn, 'speech_error', error_type=type(error).__name__)
            raise

    def stream_speech(self, text, turn):
        try:
            yield from super().stream_speech(text, turn)
            self.journal.event(self.journal_turn, 'speech_stream_completed', note='Delivery to browser, not proof of hearing.')
        except GeneratorExit:
            self.journal.event(self.journal_turn, 'speech_stream_interrupted')
            raise
        except Exception as error:
            self.journal.event(self.journal_turn, 'speech_error', error_type=type(error).__name__)
            raise

    def _reply_impl(self, turn: RecognizedTurn) -> str:
        with self._turn_lock:
            self.profile.refresh()
            observations = list(self.observations()) + self.shared_window_observations
            observations=[o for o in observations if not (o.kind.startswith(('foreground','desktop')) and not self.profile.allowed('desktop_context'))
                and not (o.kind.startswith(('visible','camera')) and not self.profile.allowed('camera'))]
            decision = decide(turn.text, turn.language, self.memory.facts() if self.profile.allowed('memory_recall') else [])
            # Short app commands can be language-labelled ambiguously by STT;
            # the command parser only accepts explicit English launch phrases.
            local_command=parse_command(turn.text, self.agent_tools.apps)
            task_plan=plan_request(turn.text, self.agent_tools.apps)
            self.journal.event(self.journal_turn, 'decision_route', route='local_'+local_command[0] if local_command else decision.route, source=decision.source,
                               bypass_reply_model=decision.answer is not None or local_command is not None or task_plan is not None)
            if decision.answer is None and local_command is None and task_plan is None:
                self.decision_shadow.submit(turn.text, turn.language, self.journal, self.journal_turn, decision.route)
            settings = self.profile.data.get('context', {})
            if asks_about_eyewear(turn.text) and self.profile.allowed('camera'):
                frame = self.camera_frame() if self.camera_frame and settings.get('camera_on_request', False) else None
                if frame and self.groq_client:
                    observations.append(eyewear_observation(self.groq_client,
                        settings.get('vision_model', 'qwen/qwen3.8-27b'), frame))
                else:
                    observations.append(eyewear_observation(None, '', None))
            if decision.route == 'camera_identity':
                if not self.profile.allowed('camera'):
                    observations.append(Observation('visible_person_label','Unknown: camera access is disabled.',
                        'camera_permission',1.0,__import__('time').monotonic()))
                else:
                    frame=self.camera_frame() if self.camera_frame else None
                    observations.extend(o for o in observations if o.kind == 'visible_person_label')
                    if not frame:
                        if self.camera_request: self.camera_request()
                        observations.append(Observation('visible_person_label',
                            'Unknown: camera was off or no fresh enrolled-face match is available. The camera preview was requested.',
                            'camera_unavailable',1.0,__import__('time').monotonic()))
            def respond(text, language, bundle):
                if decision.route == 'camera_identity':
                    match=next((o.value for o in observations if o.kind=='visible_person_label'
                                and o.source=='local_enrolled_face_match_not_identity_proof'),None)
                    if match:
                        return f'I recognize this face as {match} from the locally saved photos. Is that right?'
                    return 'I cannot identify this person yet. I need the camera on and a clear match to someone saved in Profile & Memory.'
                explicit_address=bundle.get('address_request')
                self.profile.address_preference=explicit_address or (resolve_address(self.memory.facts(),language)
                    if self.profile.allowed('memory_recall') else None)
                if explicit_address:
                    return explicit_address['term']+'.' if explicit_address['scope']=='once' else 'Okay, '+explicit_address['term']+'.'
                if not self.profile.allowed('memory_recall'):
                    bundle={**bundle,'recent':[],'recent_other_sessions':[],'relevant':[],'confirmed_facts':[]}
                if text.strip().lower().rstrip('.!') in {'open camera', 'open the camera', 'turn on camera', 'turn on the camera', 'show camera', 'show my camera'}:
                    if not self.profile.allowed('camera'):
                        return 'Camera access is disabled in your permissions.'
                    if not self.camera_request:
                        return 'Open the Camera page and choose Turn camera on.'
                    self.camera_request()
                    return 'Opening the camera preview. Face analysis will load separately.'
                reminder = parse_reminder(text)
                if reminder:
                    if not self.profile.allowed('timers'):
                        return 'Reminders are disabled in your permissions.'
                    title, seconds = reminder
                    row = self.reminders.create_once(title, seconds)
                    self.journal.event(self.journal_turn, 'local_action', tool='create_reminder', reminder_id=row['id'])
                    return f'I will remind you to {title} in {seconds / 60:g} minutes. It is saved in Reminders. Keep Setta open for the notification.'
                command=local_command
                if task_plan:
                    executor=TaskExecutor(
                        DEFAULT_SKILLS,
                        lambda name,args: self.agent_tools.execute(name,args,text),
                        lambda permission: self.profile.allowed(permission),
                        lambda: bool(getattr(self.agent_tools, 'cancelled', lambda: False)()),
                    )
                    result=executor.run(task_plan)
                    self.journal.event(self.journal_turn,'local_action',tool=task_plan.steps[0].tool,result=result)
                    if result.get('status') == 'completed':
                        return 'Playing '+str(task_plan.steps[0].arguments['query'])+' on YouTube.'
                    if result.get('status') == 'disabled':
                        return result.get('reason','Browser control is disabled in your permissions.')
                    if result.get('status') == 'cancelled':
                        return 'I stopped that task.'
                    if task_plan.steps[0].tool == 'play_spotify_music' and result.get('status') == 'unverified':
                        return 'Spotify is open with that music search, but I could not verify playback.'
                    return 'YouTube opened, but playback could not be confirmed.'
                if command:
                    kind,value=command
                    name={'timer':'start_timer','search_browser':'search_browser'}.get(kind,kind)
                    args={'seconds':value} if kind=='timer' else {'app':value} if kind=='open_app' else {'query':value} if kind=='search_browser' else {'expression':value}
                    result=self.agent_tools.execute(name,args,text)
                    self.journal.event(self.journal_turn,'local_action',tool=name,result=result)
                    if result.get('status') in {'disabled','unavailable','cancelled'}:
                        return result.get('reason','That action is unavailable.')
                    if kind=='timer': return 'Timer started for '+format(value,'g')+' seconds. Keep Setta running for the notification.'
                    if kind=='open_app': return 'Opening '+str(value).replace('_',' ')+' now.'
                    if kind=='search_browser':
                        if result.get('status') == 'ok':
                            return result.get('digest','Search completed.').strip()
                        return result.get('reason','The search could not be completed.')
                    prefix='Calculator shows ' if result.get('calculator_verified') else 'The result is '
                    return prefix+result['result']+'.'+(' Calculator display could not be verified.' if kind=='calculator' and not result.get('calculator_verified') else '')
                if decision.answer is not None:
                    return decision.answer
                if desktop_question(text):
                    # Old assistant guesses are not independent desktop evidence.
                    # Keep the archive, but remove it from this desktop query.
                    bundle = {**bundle, 'recent': [], 'recent_other_sessions': [], 'relevant': []}
                compact = self.reply_provider == 'groq'
                recent = [{'role': row['role'], 'content': row['text']} for row in bundle['recent'][-(4 if compact else 6):]]
                self.history = recent + [CompanionContext.context_message(bundle,compact=compact)]
                return super(LiveConversation, self).reply(turn)
            return self.session.turn(turn.text, turn.language, respond, observations)
