"""Bounded local desktop tools. No shell execution or arbitrary file writes."""
import fnmatch
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.parse
import webbrowser

from .paths import PROJECT_ROOT
from .web_tools import WebTools
from .character_profile import CharacterProfile
from .local_actions import calculate,calculator,is_app_open_request,parse_command
from .local_timers import LocalTimers
from .paths import DATA_DIR
from .browser_media import BrowserMedia
from .spotify_media import SpotifyMedia

TOOL_PERMISSIONS={'calculate':'arithmetic','calculator':'desktop_apps','start_timer':'timers',
    'open_app':'desktop_apps','open_file':'desktop_apps','find_files':'file_search',
    'get_weather':'internet','search_web':'internet','search_browser':'internet',
    'play_youtube_music':'browser_navigation',
    'play_spotify_music':'desktop_apps',
    'get_desktop_context':'desktop_context',
    'search_conversation_memory':'memory_recall'}


def schema(name, description, properties, required=()):
    return {'type':'function','function':{'name':name,'description':description,
        'parameters':{'type':'object','properties':properties,'required':list(required),'additionalProperties':False}}}


class DesktopTools:
    def __init__(self, observations=lambda:[], roots=None, launcher=None, memory=None):
        self.observations = observations
        self.roots = [Path(root).resolve() for root in (roots if roots is not None else [PROJECT_ROOT])]
        self.launcher = launcher or os.startfile
        self.cancelled = lambda: False
        self.memory = memory
        self.web = WebTools()
        self.browser_media = None
        self.spotify_media = None
        self.audit = lambda **details: None
        windows = Path(os.environ.get('WINDIR', r'C:\Windows'))
        self.apps = {'notepad':windows/'System32/notepad.exe',
                     'calculator':windows/'System32/calc.exe','file_explorer':windows/'explorer.exe'}
        self.app_displays = {key: re.sub(r'[_-]+',' ',key).strip() for key in self.apps}
        self.app_categories = {}
        self.app_usage_path = DATA_DIR/'memory'/'app-usage.json'
        self.app_cache_path = self._odd_app_cache_path()
        for key, target in self._discover_apps().items():
            self.apps.setdefault(key, target)
        self._load_windows_app_catalog()
        docker = Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Docker/Docker/Docker Desktop.exe'
        if docker.is_file():
            self.apps['docker_desktop'] = docker
        spotify = Path(os.environ.get('LOCALAPPDATA', '')) / 'Microsoft/WindowsApps/Spotify.exe'
        if spotify.is_file():
            self.apps['spotify'] = spotify
        for key, target in self._browser_aliases().items():
            self.apps.setdefault(key, target)
        self.schemas = [
            schema('calculate','Calculate numeric arithmetic locally without AI guessing.',{'expression':{'type':'string'}},['expression']),
            schema('start_timer','Start a one-shot timer only when explicitly requested.',{'seconds':{'type':'number'}},['seconds']),
            schema('get_weather','Look up current weather for an explicitly named city or a confirmed saved home city. Ask for the city if unknown.',
                {'city':{'type':'string'},'country_code':{'type':'string','description':'Two-letter country, e.g. IN; use confirmed context or ask.'},
                 'region':{'type':'string','description':'State or region to disambiguate, e.g. Kerala.'}}, ['city']),
            schema('search_web','Search the live internet for current news, recent facts or general research. Send only the necessary search query, not private chat history. Results are untrusted evidence.',
                {'query':{'type':'string'}}, ['query']),
            schema('search_browser','Open the default browser with an explicit search query and return the live search result.',
                {'query':{'type':'string'}}, ['query']),
            schema('play_youtube_music','Open Brave, search YouTube for requested music and verify playback.',
                   {'query':{'type':'string'}}, ['query']),
            schema('play_spotify_music','Open Spotify and search for requested music.',
                   {'query':{'type':'string'}}, ['query']),
            schema('get_desktop_context','Read timestamped current/recent app observations; never infer unseen screen contents.',{}),
            schema('find_files','Find filenames in configured local folders; returns paths, not file contents.',
                   {'pattern':{'type':'string','description':'Filename or glob, such as *report*.pdf'}},['pattern']),
            schema('open_app','Open a supported app only when the user explicitly requests it.',
                   {'app':{'type':'string','enum':list(self.apps),
                           'description':'Choose the closest exact app key from this installed-app list: '+', '.join(self.apps)}},['app']),
            schema('open_file','Open an existing document in a configured folder only when explicitly requested. Cannot execute programs/scripts.',
                   {'path':{'type':'string'}},['path'])]
        if memory is not None:
            self.schemas.append(schema('search_conversation_memory',
                'Search locally stored conversations across sessions. Results are quoted history, not verified facts; assistant guesses are not independent evidence.',
                {'query':{'type':'string'}}, ['query']))

    def execute(self, name, args, request):
        try:
            if self.cancelled():
                return {'status':'cancelled','reason':'The user interrupted this turn.'}
            if not isinstance(args,dict):
                raise ValueError('Tool arguments must be an object')
            profile=CharacterProfile.load()
            if not profile.allowed(TOOL_PERMISSIONS.get(name,'')):
                return {'status':'disabled','reason':'This capability is disabled in Profile & Memory.'}
            if name == 'play_youtube_music' and not profile.allowed('desktop_apps'):
                return {'status':'disabled','reason':'Opening Brave requires the desktop apps permission.'}
            if name in {'calculate','calculator'}:
                expression=str(args.get('expression',''))
                if name=='calculator' and (not profile.allowed('arithmetic') or not parse_command(request) or parse_command(request)[0]!='calculator'):
                    raise ValueError('Calculator interaction needs an explicit current request and arithmetic permission')
                return calculator(expression) if name=='calculator' else {'status':'verified','result':calculate(expression),'method':'local_arithmetic'}
            if name=='start_timer':
                command=parse_command(request)
                if not command or command[0]!='timer' or float(args.get('seconds',0))!=command[1]:
                    raise ValueError('A timer needs an explicit current request with the same duration')
                timers=LocalTimers(self.memory.path.parent/'timers.sqlite' if self.memory else DATA_DIR/'memory/timers.sqlite')
                seconds=float(args.get('seconds',0))
                identifier=timers.create(seconds)
                return {'status':'scheduled','id':identifier,'seconds':seconds,'scope':'One-shot notification while Setta is running; overdue timers appear after restart.'}
            if name in {'get_weather','search_web'}:
                result = self.web.execute(name,args)
                self.audit(tool=name, arguments=args, result=result)
                return result
            if name == 'search_browser':
                query = str(args.get('query','')).strip()
                if not query or len(query) > 240:
                    raise ValueError('Use a short search query')
                webbrowser.open('https://www.google.com/search?q='+urllib.parse.quote_plus(query))
                result = self.web.execute('search_web', {'query': query})
                result['browser_opened'] = True
                return result
            if name == 'play_youtube_music':
                browser = self.apps.get('brave')
                if not browser or not Path(browser).is_file():
                    return {'status':'unavailable','reason':'Brave is not installed or could not be located.'}
                if self.browser_media is None:
                    self.browser_media = BrowserMedia(Path(browser))
                result = self.browser_media.play_youtube(str(args.get('query','')))
                self.audit(tool=name, arguments=args, result=result)
                return result
            if name == 'play_spotify_music':
                spotify = self.apps.get('spotify')
                if not spotify or not Path(spotify).is_file():
                    return {'status':'unavailable','reason':'Spotify is not installed or could not be located.'}
                if self.spotify_media is None:
                    self.spotify_media = SpotifyMedia(Path(spotify), self.launcher)
                result = self.spotify_media.search(str(args.get('query','')))
                self.audit(tool=name, arguments=args, result=result)
                return result
            if name == 'search_conversation_memory' and self.memory is not None:
                query = str(args.get('query','')).strip()
                if not query or len(query)>200:
                    raise ValueError('Use a short memory search query')
                return {'scope':'local conversation archive', 'results':[
                    {key: row.get(key) for key in ('role','text','language','created_at')}
                    for row in self.memory.search(query, limit=3)]}
            if name == 'get_desktop_context':
                return {'observations':[o.__dict__ for o in self.observations()],
                        'scope':'App and title metadata only; not screen contents.'}
            if name == 'find_files':
                pattern = str(args.get('pattern','')).strip()
                if not pattern or len(pattern)>120 or '/' in pattern or '\\' in pattern:
                    raise ValueError('Use a filename or filename glob, not a path')
                if not any(c in pattern for c in '*?'):
                    pattern = '*'+pattern+'*'
                hits=[]; visited=0; started=time.monotonic()
                excluded={'.git','.venv','node_modules','.tools','runtime','__pycache__','memory'}
                for root in self.roots:
                    for folder, directories, names in os.walk(root, followlinks=False):
                        if time.monotonic()-started>2:
                            return {'files':hits,'bounded':True,'roots':[str(r) for r in self.roots]}
                        directories[:] = [d for d in directories if d not in excluded and not Path(folder,d).is_symlink()]
                        for filename in names:
                            visited+=1
                            path = Path(folder,filename)
                            if self._safe(path) and fnmatch.fnmatch(filename.casefold(),pattern.casefold()):
                                hits.append(str(path))
                            if len(hits)>=20 or visited>=10000 or time.monotonic()-started>2:
                                return {'files':hits,'bounded':True,'roots':[str(r) for r in self.roots]}
                return {'files':hits,'bounded':False,'roots':[str(r) for r in self.roots]}
            if name in {'open_app','open_file'}:
                if not is_app_open_request(request):
                    raise ValueError('Opening requires an explicit request in the current user turn')
                if name == 'open_app':
                    app = args.get('app')
                    command=parse_command(request,self.apps)
                    if not command or command[0]!='open_app' or command[1]!=app:
                        raise ValueError('The selected app must match the app explicitly named by the user')
                    if app not in self.apps:
                        if app == 'figma':
                            opened = webbrowser.open('figma://')
                            return {'status':'launch_requested' if opened else 'unavailable','app':'figma',
                                    'target':'figma://','verified_open':False,
                                    **({'reason':'Windows did not accept the Figma app link.'} if not opened else {})}
                        raise ValueError('Unsupported app')
                    self._launch_target(self.apps[app])
                    self._record_app_launch(app)
                    return {'status':'launch_requested','app':app,'display_name':self.app_displays.get(app,app),
                            'target':str(self.apps[app]),'verified_open':False}
                path = Path(str(args.get('path',''))).resolve()
                allowed={'.txt','.md','.pdf','.png','.jpg','.jpeg','.webp','.wav','.mp3','.mp4','.docx','.xlsx','.pptx'}
                if not self._safe(path) or not path.is_file() or path.suffix.casefold() not in allowed:
                    raise ValueError('Only existing permitted documents inside configured folders can be opened')
                self.launcher(str(path))
                return {'status':'launch_requested','path':str(path),'verified_open':False}
            raise ValueError('Unknown tool')
        except (OSError,ValueError,TypeError) as error:
            return {'status':'unavailable','reason':str(error)}

    def execute_resolved_app(self, app, request):
        """Launch a catalog ID chosen by the local resolver or explicit user choice."""
        try:
            if self.cancelled():
                return {'status':'cancelled','reason':'The user interrupted this turn.'}
            profile=CharacterProfile.load()
            if not profile.allowed('desktop_apps'):
                return {'status':'disabled','reason':'This capability is disabled in Profile & Memory.'}
            if not is_app_open_request(request):
                return {'status':'unavailable','reason':'Opening requires an explicit request in the current user turn'}
            if app not in self.apps:
                return {'status':'unavailable','reason':'Unsupported app'}
            self._launch_target(self.apps[app])
            self._record_app_launch(app)
            return {'status':'launch_requested','app':app,'display_name':self.app_displays.get(app,app),
                    'target':str(self.apps[app]),'verified_open':False}
        except (OSError,ValueError,TypeError) as error:
            return {'status':'unavailable','reason':str(error)}

    def close(self):
        if self.browser_media is not None:
            self.browser_media.close()

    def _safe(self, path):
        path=path.resolve()
        if not any(path.is_relative_to(root) for root in self.roots):
            return False
        return not any(part.casefold() in {'.git','.venv','.tools','.env','runtime','memory'} or
                       part.casefold().startswith('.env.') for part in path.parts)

    def _discover_apps(self):
        """Expose installed user-facing apps without granting arbitrary path execution."""
        folders = [Path(os.environ.get('ProgramFiles', r'C:\Program Files')),
                    Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')),
                    Path(os.environ.get('LOCALAPPDATA', r'C:\Users\Default\AppData\Local'))]
        apps = {}
        blocked = {'uninstall', 'unins', 'update', 'updater', 'crashpad', 'helper',
                   'service', 'setup', 'install', 'maintenanceservice', 'bash',
                   'cmd', 'command', 'conhost', 'git', 'node', 'npm', 'pwsh',
                   'powershell', 'python', 'pythonw', 'terminal', 'wt', 'wsl'}
        shortcut_folders = [
            Path(os.environ.get('PROGRAMDATA', r'C:\ProgramData')) /
                'Microsoft/Windows/Start Menu/Programs',
            Path(os.environ.get('APPDATA', r'C:\Users\Default\AppData\Roaming')) /
                'Microsoft/Windows/Start Menu/Programs',
        ]
        for folder in shortcut_folders:
            if not folder.is_dir():
                continue
            try:
                candidates = folder.rglob('*.lnk')
            except OSError:
                continue
            for path in candidates:
                name = path.stem.casefold()
                if any(part in name for part in blocked):
                    continue
                key = re.sub(r'[^a-z0-9]+', '_', name).strip('_')
                if key and key not in apps:
                    apps[key] = path
        for folder in folders:
            if not folder.is_dir():
                continue
            try:
                candidates = folder.glob('*/*/*.exe')
            except OSError:
                continue
            for path in candidates:
                name = path.stem.casefold()
                if any(part in name for part in blocked):
                    continue
                key = re.sub(r'[^a-z0-9]+', '_', path.stem.casefold()).strip('_')
                if key and key not in apps:
                    apps[key] = path
        return apps

    def _browser_aliases(self):
        brave = Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / \
            'BraveSoftware/Brave-Browser/Application/brave.exe'
        if brave.is_file():
            self.apps['brave'] = brave
            return {'browser': brave}
        for name in ('chrome', 'msedge', 'edge', 'firefox', 'brave', 'opera'):
            if name in self.apps:
                target = self.apps[name]
                if name == 'brave' and str(target).lower().endswith('.lnk'):
                    known = Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / \
                        'BraveSoftware/Brave-Browser/Application/brave.exe'
                    if known.is_file():
                        self.apps[name] = known
                        target = known
                return {'browser': target}
        return {}

    def _odd_app_cache_path(self):
        candidates=[]
        if os.environ.get('LOCALAPPDATA'):
            candidates.append(Path(os.environ['LOCALAPPDATA'])/'ODD/apps_cache.json')
        if os.environ.get('USERPROFILE'):
            candidates.append(Path(os.environ['USERPROFILE'])/'AppData/Local/ODD/apps_cache.json')
        candidates.append(Path.home()/'AppData/Local/ODD/apps_cache.json')
        return next((path for path in candidates if path.is_file()), candidates[0] if candidates else Path('ODD/apps_cache.json'))

    def _load_windows_app_catalog(self):
        """Load ODD's display, target and category fields without losing Windows target forms."""
        catalog = self.app_cache_path
        if not catalog.is_file():
            return {}
        try:
            rows = json.loads(catalog.read_text(encoding='utf-8'))
        except (OSError, ValueError, TypeError):
            return {}
        apps = {}
        for row in rows:
            if not isinstance(row, list) or len(row) < 2:
                continue
            display, target = str(row[0]).strip(), str(row[1]).strip()
            category = str(row[2]).strip() if len(row)>2 else ''
            key = re.sub(r'[^a-z0-9]+', '_', display.casefold()).strip('_')
            if not key or not self._catalog_target_allowed(target):
                continue
            previous=apps.get(key)
            if previous and self._target_quality(previous[0]) >= self._target_quality(target):
                continue
            apps[key]=(target,display,category)
        for key,(target,display,category) in apps.items():
            self.apps.setdefault(key,target)
            self.app_displays[key]=display
            self.app_categories[key]=category
        return {key:row[0] for key,row in apps.items()}

    @staticmethod
    def _target_quality(target):
        target=str(target)
        if target.startswith('{'): return 1
        if target.lower().endswith(('.exe','.lnk','.url')): return 3
        if '!' in target: return 4
        return 2

    def _record_app_launch(self, app):
        """Store local launch counts as a weak preference signal, not proof of use."""
        try:
            self.app_usage_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                value=json.loads(self.app_usage_path.read_text(encoding='utf-8'))
                if not isinstance(value,dict): value={}
            except (OSError,ValueError,TypeError):
                value={}
            row=value.get(app,{})
            if not isinstance(row,dict): row={}
            row['launch_requests']=int(row.get('launch_requests',0))+1
            row['last_launch_request']=time.time()
            value[app]=row
            self.app_usage_path.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
        except (OSError,ValueError,TypeError):
            pass

    def app_candidates(self, category, limit=5, observed_apps=()):
        """Return installed category candidates ranked by metadata and observed foreground use."""
        aliases={
            'design':('figma','photoshop','illustrator','affinity','sketch','canva','blender','krita','gimp','paint','fusion','designer','draw'),
            'browser':('chrome','edge','firefox','brave','opera','vivaldi','browser'),
            'code':('code','visual studio','cursor','pycharm','intellij','eclipse','sublime','notepad++','zed','android studio'),
            'communication':('teams','slack','discord','zoom','whatsapp','telegram','signal','meet'),
            'music':('spotify','itunes','musicbee','foobar','winamp'),
            'video':('premiere','resolve','capcut','vegas pro','shotcut','kdenlive'),
            'photo':('photoshop','lightroom','paint','gimp','photos','irfanview','affinity photo'),
            'files':('file explorer','7-zip','winrar','peazip'),
        }
        catalog_aliases={
            'design':('design','creative','graphics','drawing'),
            'browser':('browser','web'),
            'code':('code','coding','development','programming','developer','ide'),
            'communication':('communication','messaging','chat'),
            'music':('music','audio'),
            'video':('video','editing'),
            'photo':('photo','image','photography'),
            'files':('file','archive','compression'),
        }
        hints=aliases.get(category,(category,))
        def normalize(value):
            return re.sub(r'[^a-z0-9]+','',Path(str(value)).stem.casefold())
        observed={}
        for value in observed_apps:
            normalized=normalize(value)
            observed[normalized]=observed.get(normalized,0)+1
        try:
            usage=json.loads(self.app_usage_path.read_text(encoding='utf-8'))
            if not isinstance(usage,dict): usage={}
        except (OSError,ValueError,TypeError): usage={}
        families={}
        products={'google chrome':'chrome','chrome':'chrome','microsoft edge':'edge','edge':'edge',
                  'brave browser':'brave','brave':'brave','mozilla firefox':'firefox','firefox':'firefox',
                  'zoom workplace':'zoom','zoom launcher':'zoom','zoom':'zoom'}
        for key,target in self.apps.items():
            display=self.app_displays.get(key,key)
            name=(key+' '+display).casefold().replace('_',' ')
            lowered_target=str(target).casefold()
            if key.startswith(('restart','uninstall','update','setup','helper')) or 'ms-settings:' in lowered_target:
                continue
            matched=[hint for hint in hints if re.search(r'(?<![a-z0-9])'+re.escape(hint)+r'(?![a-z0-9])',name)]
            catalog_category=str(self.app_categories.get(key,'' )).casefold()
            category_match=any(re.search(r'(?<![a-z0-9])'+re.escape(alias)+r'(?![a-z0-9])',catalog_category)
                              for alias in catalog_aliases.get(category,(category,)))
            if category_match and not matched:
                matched=[category]
            if not matched: continue
            if category=='design' and any(token in name for token in ('repair','update','installer','setup','crash','helper')):
                continue
            row=usage.get(key,{})
            count=int(row.get('launch_requests',0)) if isinstance(row,dict) else 0
            observed_count=sum(count for app_name,count in observed.items() if app_name in {
                normalize(key),normalize(display),normalize(target)})
            candidate={'app':key,'display_name':display,'category':self.app_categories.get(key,''),'launch_requests':count,
                       'observed_history_matches':observed_count,
                       'score':len(matched)*100+observed_count*25}
            display_family=re.sub(r'[^a-z0-9]+',' ',display.casefold()).strip()
            family=products.get(display_family,re.sub(r'[^a-z0-9]+','',display.casefold()))
            previous=families.get(family)
            if previous is None or candidate['score']>previous['score'] or (
                    candidate['score']==previous['score'] and
                    self._target_quality(target)>self._target_quality(self.apps[previous['app']])):
                families[family]=candidate
        result=list(families.values())
        concrete={row['display_name'].casefold() for row in result
                  if row['display_name'].casefold() not in {'browser','web browser','internet browser'}}
        if concrete:
            result=[row for row in result if row['display_name'].casefold() not in {'browser','web browser','internet browser'}]
        hint_rank={hint:index for index,hint in enumerate(hints)}
        for row in result:
            name=(row['app']+' '+row['display_name']).casefold().replace('_',' ')
            row['default_rank']=min((rank for hint,rank in hint_rank.items()
                                     if re.search(r'(?<![a-z0-9])'+re.escape(hint)+r'(?![a-z0-9])',name)),
                                    default=len(hints))
        return sorted(result,key=lambda row:(row['observed_history_matches'],-row['default_rank'],
                                               row['score'],row['display_name'].casefold()),reverse=True)[:limit]

    def resolve_app_reference(self, reference):
        """Resolve a remembered display name to one installed catalog ID."""
        wanted=re.sub(r'[^a-z0-9]+',' ',str(reference).casefold()).strip()
        if not wanted:
            return None
        exact=[]
        partial=[]
        for app in self.apps:
            labels=(app,self.app_displays.get(app,''))
            normalized=[re.sub(r'[^a-z0-9]+',' ',str(label).casefold()).strip() for label in labels]
            if wanted in normalized:
                exact.append(app)
            elif any(re.search(r'(?<![a-z0-9])'+re.escape(wanted)+r'(?![a-z0-9])',label)
                     for label in normalized if label):
                partial.append(app)
        matches=exact or partial
        targets={str(self.apps[app]) for app in matches}
        if len(targets)==1 and matches:
            return matches[0]
        return matches[0] if len(matches)==1 else None

    def best_app_match(self, candidates, observed_apps=()):
        """Choose the strongest parsed app match, preferring permissioned observed use."""
        if not candidates:
            return None
        observed={}
        for value in observed_apps:
            normalized=re.sub(r'[^a-z0-9]+','',Path(str(value)).stem.casefold())
            observed[normalized]=observed.get(normalized,0)+1
        def usage(app):
            values=(app,self.app_displays.get(app,app),self.apps.get(app,''))
            aliases={re.sub(r'[^a-z0-9]+','',Path(str(value)).stem.casefold()) for value in values}
            return sum(count for name,count in observed.items() if name in aliases)
        return max(candidates,key=usage)

    @staticmethod
    def _catalog_target_allowed(target):
        if target.startswith(('ms-settings:', 'shell:')):
            return True
        if re.fullmatch(r'[A-Za-z0-9_.-]+![A-Za-z0-9_.-]+', target):
            return True
        if re.fullmatch(r'[A-Za-z0-9_.-]+',target):
            return True
        if re.fullmatch(r'\{[A-Fa-f0-9-]{36}\}\\[A-Za-z0-9_ .()\\-]+\.(?:exe|msc|cpl|chm|txt)',target,re.I):
            return True
        if target.lower().endswith(('.exe', '.lnk', '.url')):
            return Path(target).is_file()
        if target.lower().endswith(('.msc','.cpl')) and re.fullmatch(r'[A-Za-z]:\\[A-Za-z0-9_ .()\\-]+\.(?:msc|cpl)',target,re.I):
            return True
        return False

    def _launch_target(self, target):
        target = str(target)
        if target.startswith('shell:') or '!' in target and not Path(target).is_file():
            os.startfile('shell:AppsFolder\\' + target.removeprefix('shell:AppsFolder\\'))
        elif target.startswith('ms-settings:'):
            os.startfile(target)
        elif re.fullmatch(r'[A-Za-z0-9_.-]+',target) and not Path(target).is_file():
            try:
                self.launcher(target)
            except OSError:
                os.startfile('shell:AppsFolder\\'+target)
        elif target.startswith('{') and '}\\' in target:
            import winreg
            root,relative=target.split('}\\',1)
            root_guid=root+'}'
            registry_roots=(winreg.HKEY_LOCAL_MACHINE,winreg.HKEY_CURRENT_USER)
            resolved=None
            for registry_root in registry_roots:
                try:
                    with winreg.OpenKey(registry_root,rf'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FolderDescriptions\\{root_guid}\\PropertyBag') as key:
                        base=winreg.QueryValueEx(key,'Path')[0]
                    candidate=Path(base)/relative
                    if candidate.is_file():
                        resolved=candidate
                        break
                except OSError:
                    continue
            if resolved is None:
                raise OSError('The app target folder is unavailable.')
            self.launcher(str(resolved))
        elif Path(target).is_file() or target.lower().endswith(('.lnk', '.url')):
            self.launcher(target)
        else:
            try:
                self.launcher(target)
            except OSError:
                os.startfile('shell:AppsFolder\\' + target)
