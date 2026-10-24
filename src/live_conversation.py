"""Memory-enabled Sarvam adapter shared by text and microphone entry points."""
from pathlib import Path
import json
import re
import threading
import time
from uuid import uuid4

from .companion_context import CompanionContext, ConversationSession, Observation
from .companion_memory import CompanionMemory
from .paths import DATA_DIR
from .sarvam_conversation import RecognizedTurn, SarvamConversation
from .camera_context import asks_about_eyewear, eyewear_observation
from .desktop_activity import desktop_question
from .agent_tools import DesktopTools
from .conversation_journal import ConversationJournal
from .decision_router import asks_for_current_facts, decide
from .laya_shadow import LayaShadow
from .local_actions import app_task_reference_request, is_affirmative, is_app_open_request, is_negative, normalize_app_task, parse_command
from .address_preferences import resolve_address
from .local_reminders import LocalReminders
from .reminder_intent import parse_reminder
from .task_planner import plan_request
from .task_execution import TaskExecutor
from .skill_registry import DEFAULT_SKILLS
from .personality_preferences import parse_personality_correction
from .location_lookup import asks_for_device_location, answer_current_location
from .study_check import is_study_checkin, study_checkin_reply


def app_category_request(text, language=None):
    """Recognize a broad requested app category, leaving brand choice to inventory."""
    value=text.strip().casefold().rstrip('?.!')
    remembered_category=app_task_reference_request(text,language)
    if remembered_category:
        return remembered_category
    has_action=bool(re.search(r'\b(?:open|launch|start|bring up|pull up|run|show me|take me to)\b',value))
    patterns={
        'design':r'\b(?:(?:graphic|ui) design|design|drawing|creative)(?:\s+(?:apps?|programs?|software|tools?))?\b',
        'browser':r'\b(?:web )?browsers?\b',
        'code':r'\b(?:coding|code editor|programming|ide)(?:\s+(?:apps?|programs?|tools?))?\b',
        'communication':r'\b(?:messaging|chat|communication)(?:\s+(?:apps?|programs?|tools?))?\b',
        'music':r'\b(?:music|audio)(?:\s+(?:apps?|players?))?\b',
        'video':r'\bvideo(?:\s+(?:editing\s+)?(?:apps?|editors?|programs?))?\b',
        'photo':r'\b(?:photo|image)(?:\s+(?:editing\s+)?(?:apps?|editors?|programs?))?\b',
        'files':r'\b(?:file managers?|archive managers?)\b',
    }
    category=next((category for category,pattern in patterns.items() if re.search(pattern,value)),None)
    if category and (has_action or re.fullmatch(r'(?:my |the )?.+?\s+(?:apps?|programs?|tools?|software|browsers?)',value)):
        return category
    return None


class LiveConversation(SarvamConversation):
    def __init__(self, api_key: str, *, memory_path: Path | None = None,
                 session_id: str | None = None, observations=None, camera_frame=None, camera_request=None,
                 location_provider=None, study_check=None, **kwargs):
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
        self.study_check = study_check
        self.location_provider = location_provider
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
        location_request = asks_for_device_location(turn.text)
        if not self._recognized_pending:
            self.journal_turn = self.journal.new_turn()
        self._recognized_pending = False
        self.journal.event(self.journal_turn, 'user_text',
                           text='[explicit location request]' if location_request else turn.text,
                           language=turn.language)
        self.last_route = None
        try:
            if location_request:
                self.last_route = {'route': 'local_location', 'provider': 'Windows Geolocator + offline GeoNames'}
                reply = answer_current_location(self.location_provider, self.profile, turn.language)
                self.journal.event(self.journal_turn, 'location_lookup', result='redacted from diagnostics')
                self.journal.event(self.journal_turn, 'reply_generated', text='[location reply redacted]',
                                   language=turn.language, note='Location replies are not stored in chat memory.')
                return reply
            reply = self._reply_impl(turn)
            if self.last_route:
                self.journal.event(self.journal_turn, 'model_route', **self.last_route)
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
            if not asks_for_device_location(turn.text):
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
            if is_study_checkin(turn.text):
                status = 'unknown'
                result = None
                if self.profile.allowed('camera') and self.study_check:
                    result = self.study_check()
                    if isinstance(result, dict):
                        status = result.get('phone_status', 'unknown')
                    elif result in {'present', 'absent'}:
                        status = result
                sent = bool(isinstance(result, dict) and result.get('image_sent'))
                title_sent = bool(isinstance(result, dict) and result.get('title_sent'))
                self.last_route = {'route': 'study_checkin', 'provider': 'Groq' if sent or title_sent else 'screen context/local'}
                self.journal.event(self.journal_turn, 'study_checkin', phone_status=status,
                                   content_status=result.get('content_status', 'unknown') if isinstance(result, dict) else 'unknown',
                                   title_sent=title_sent,
                                   image_saved=False, image_sent=sent)
                return study_checkin_reply(turn.language, result)
            if turn.language == 'en-IN' and asks_for_current_facts(turn.text):
                self.last_route = {'route': 'live_search', 'provider': 'configured web search'}
                self.journal.event(self.journal_turn, 'decision_route', route='live_search',
                                   source='freshness_rule', bypass_reply_model=True)
                result = self.agent_tools.execute('search_web', {'query': turn.text}, turn.text)
                if result.get('status') != 'ok' or not result.get('browser_executed'):
                    self.journal.event(self.journal_turn, 'current_fact_search', status='unverified')
                    return 'I could not verify that with live sources just now, so I do not want to guess.'
                self.journal.event(self.journal_turn, 'current_fact_search', status='verified',
                                   sources=[row.get('url') for row in result.get('sources', []) if row.get('url')])
                digest = str(result.get('digest', '')).strip()
                if not digest:
                    return 'I could not verify that with live sources just now, so I do not want to guess.'
                digest = re.sub(r'\[([^\]]+)\]\(https?://[^)]+\)', r'\1', digest)
                digest = re.sub(r'https?://\S+', '', digest).strip()
                source_names = list(dict.fromkeys(
                    str(row.get('title', '')).strip() for row in result.get('sources', [])
                    if str(row.get('title', '')).strip()))
                if source_names:
                    digest = digest.rstrip() + '\nSource: ' + '; '.join(source_names[:3])
                return digest
            preference_correction = parse_personality_correction(turn.text)
            observations = list(self.observations()) + self.shared_window_observations
            observations=[o for o in observations if not (o.kind.startswith(('foreground','desktop')) and not self.profile.allowed('desktop_context'))
                and not (o.kind.startswith(('visible','camera')) and not self.profile.allowed('camera'))]
            decision = decide(turn.text, turn.language, self.memory.facts() if self.profile.allowed('memory_recall') else [])
            local_command=None
            chosen_app=None
            local_command=parse_command(turn.text, self.agent_tools.apps)
            if local_command and local_command[0]=='choose_app':
                observed_apps=[]
                if self.profile.allowed('desktop_context'):
                    for observation in observations:
                        if observation.kind=='recent_desktop_activity':
                            try:
                                observed_apps.extend(row.get('app','') for row in json.loads(observation.value)
                                                    if isinstance(row,dict))
                            except (ValueError,TypeError,AttributeError):
                                continue
                chosen_app=self.agent_tools.best_app_match(local_command[1],observed_apps)
                local_command=('open_app',chosen_app)
            task_plan=plan_request(turn.text, self.agent_tools.apps)
            self.journal.event(self.journal_turn, 'decision_route', route='local_'+local_command[0] if local_command else decision.route, source=decision.source,
                               bypass_reply_model=decision.answer is not None or local_command is not None or task_plan is not None)
            if decision.answer is None and local_command is None and task_plan is None and not preference_correction:
                self.decision_shadow.submit(turn.text, turn.language, self.journal, self.journal_turn, decision.route)
            settings = self.profile.data.get('context', {})
            category=app_category_request(turn.text,turn.language)
            # Specific playback intent must win over the broad "open a music app" fallback.
            if category and local_command is None and task_plan is None:
                remembered_app=None
                if self.profile.allowed('memory_recall'):
                    relation_key='user_uses_app_for_'+category
                    relation=next((row for row in self.memory.facts() if row['key']==relation_key),None)
                    if relation:
                        remembered_app=self.agent_tools.resolve_app_reference(relation['value'])
                observed_apps=[]
                if self.profile.allowed('desktop_context'):
                    try:
                        for observation in observations:
                            if observation.kind == 'recent_desktop_activity':
                                rows=json.loads(observation.value)
                                observed_apps.extend(row.get('app','') for row in rows if isinstance(row,dict))
                    except (ValueError,TypeError,AttributeError):
                        observed_apps=[]
                candidates=self.agent_tools.app_candidates(category,observed_apps=observed_apps)
                selected=remembered_app or (candidates[0]['app'] if candidates else None)
                if selected:
                    result=self.agent_tools.execute_resolved_app(selected,turn.text)
                    if result.get('status')=='launch_requested':
                        display=result.get('display_name') or self.agent_tools.app_displays.get(selected,selected)
                        return 'Opening '+display+'.'
                    return result.get('reason','I could not open that app.')
                return 'I could not find an installed '+category+' app.'
            if local_command is None and is_app_open_request(turn.text):
                return 'I could not find a matching installed app.'
            pending_personality = getattr(self, '_pending_personality', None)
            if pending_personality:
                self._pending_personality = None
                if time.monotonic() < pending_personality['expires_at']:
                    if is_affirmative(turn.text):
                        try:
                            self.profile = self.profile.save_preferences(pending_personality['values'],
                                getattr(self.profile, '_path', None))
                        except (OSError, ValueError):
                            return 'I could not save that preference. You can still change it in Profile & Memory.'
                        return self._personality_saved_reply(pending_personality['language'])
                    if is_negative(turn.text):
                        return self._personality_cancelled_reply(pending_personality['language'])
            if turn.text.strip().casefold().rstrip('.!?') in {'yes', 'yes please', 'yeah', 'yep', 'sure', 'go ahead', 'do it', 'okay', 'ok'}:
                return 'I do not have a pending action to confirm. Tell me what you would like me to do.'
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
                correction = preference_correction
                preference_save_failed = False
                if correction:
                    if correction.persistent:
                        try:
                            self.profile = self.profile.save_preferences(correction.values,
                                getattr(self.profile, '_path', None))
                        except (OSError, ValueError):
                            if correction.command_only:
                                return 'I could not save that preference. You can change it in Profile & Memory.'
                            self.profile.turn_personality_overrides = correction.values
                            preference_save_failed = True
                    else:
                        if not correction.command_only:
                            self.profile.turn_personality_overrides = correction.values
                    if correction.command_only:
                        if correction.persistent:
                            return self._personality_saved_reply(language)
                        self._pending_personality = {'values': correction.values, 'language': language,
                            'expires_at': time.monotonic()+90}
                        return self._personality_one_off_reply(language)
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
                if text.strip().lower().rstrip('.!?') in {'open camera', 'open the camera', 'turn on camera', 'turn on the camera', 'show camera', 'show my camera'}:
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
                    if chosen_app:
                        value=chosen_app
                    name={'timer':'start_timer','search_browser':'search_browser'}.get(kind,kind)
                    args={'seconds':value} if kind=='timer' else {'app':value} if kind=='open_app' else {'query':value} if kind=='search_browser' else {'expression':value}
                    authorized_request=text
                    if kind=='open_app' and chosen_app:
                        authorized_request='Open '+str(value).replace('_',' ')
                    elif kind=='open_app' and local_command and local_command[0]=='open_app' and parse_command(text,self.agent_tools.apps)==local_command:
                        authorized_request='Open '+str(value).replace('_',' ')
                    result=(self.agent_tools.execute_resolved_app(value,authorized_request)
                            if kind=='open_app' and chosen_app else self.agent_tools.execute(name,args,authorized_request))
                    self.journal.event(self.journal_turn,'local_action',tool=name,result=result)
                    if result.get('status') in {'disabled','unavailable','cancelled'}:
                        if kind == 'open_app' and result.get('status') == 'unavailable' and result.get('reason') == 'Unsupported app':
                            return result.get('reason','That action is unavailable.')
                        return result.get('reason','That action is unavailable.')
                    if kind=='timer': return 'Timer started for '+format(value,'g')+' seconds. Keep Setta running for the notification.'
                    if kind=='open_app':
                        display=result.get('display_name',str(value).replace('_',' '))
                        return 'Opening '+display+'.'
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
                try:
                    answer = super(LiveConversation, self).reply(turn)
                    if correction and ((not correction.persistent and not correction.command_only)
                                       or preference_save_failed):
                        self._pending_personality = {'values': correction.values, 'language': language,
                            'expires_at': time.monotonic()+90}
                        prompt = self._personality_question(language)
                        if preference_save_failed:
                            prompt = 'I could not save that preference yet. ' + prompt
                        answer = answer.rstrip() + ' ' + prompt
                    return answer
                finally:
                    if correction and (not correction.persistent or preference_save_failed):
                        self.profile.turn_personality_overrides = {}
            try:
                return self.session.turn(turn.text, turn.language, respond, observations)
            finally:
                self.profile.turn_personality_overrides = {}

    @staticmethod
    def _personality_question(language):
        return {
            'en-IN': 'Would you like me to make that your default?',
            'hi-IN': 'क्या आप इसे अपनी स्थायी पसंद बनाना चाहेंगे?',
            'ml-IN': 'ഇത് നിങ്ങളുടെ സ്ഥിരം ഇഷ്ടമാക്കട്ടേ?',
        }.get(language, 'Would you like me to make that your default?')

    @classmethod
    def _personality_one_off_reply(cls, language):
        return {
            'en-IN': 'I’ll do that for this reply. ' + cls._personality_question(language),
            'hi-IN': 'इस जवाब में ऐसा करूँगी। ' + cls._personality_question(language),
            'ml-IN': 'ഈ മറുപടിയിൽ അങ്ങനെ ചെയ്യാം. ' + cls._personality_question(language),
        }.get(language, 'I’ll do that for this reply. ' + cls._personality_question(language))

    @staticmethod
    def _personality_saved_reply(language):
        return {
            'en-IN': 'Got it. I’ve saved that as your default in Profile & Memory.',
            'hi-IN': 'समझ गई। मैंने इसे Profile & Memory में आपकी स्थायी पसंद के रूप में सहेज दिया है।',
            'ml-IN': 'മനസ്സിലായി. ഇത് Profile & Memory-ൽ സ്ഥിരം ഇഷ്ടമായി സൂക്ഷിച്ചു.',
        }.get(language, 'Got it. I’ve saved that as your default in Profile & Memory.')

    @staticmethod
    def _personality_cancelled_reply(language):
        return {
            'en-IN': 'Okay. I’ll keep it to that reply.',
            'hi-IN': 'ठीक है। मैं इसे सिर्फ इसी जवाब तक रखूँगी।',
            'ml-IN': 'ശരി. ആ മറുപടിയിൽ മാത്രം പാലിക്കാം.',
        }.get(language, 'Okay. I’ll keep it to that reply.')
