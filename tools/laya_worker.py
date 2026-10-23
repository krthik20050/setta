"""Private JSON-lines subprocess. Local model inference; no tools or actions."""
import contextlib
import json
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
sys.stdin.reconfigure(encoding='utf-8')
try:
    with contextlib.redirect_stdout(sys.stderr):
        import torch
        torch.set_num_threads(2)
        from laya import Router
        router = Router(device='cpu', max_loaded=1)
    for line in sys.stdin:
        request = json.loads(line)
        started = time.perf_counter()
        question = {'route': {'type':'choice', 'instructions':'Choose the main next step for this request. Classify only; do not perform actions. Abstain toward reply_model when uncertain.',
            'criteria': {'reply_model':'An ordinary conversational answer or an unclear request',
                'memory_search':'Recall information from earlier conversations',
                'camera_observation':'Answer a question about what the camera can currently see',
                'desktop_context':'Read current or recent desktop activity',
                'desktop_action':'An explicit request to open an application or find a file',
                'play_media':'A request to play music, a song, a playlist or a video using Spotify or YouTube',
                'multi_step_task':'A request requiring multiple approved actions to reach a goal'}}}
        with contextlib.redirect_stdout(sys.stderr):
            result = router.predict(request['text'][:1500], question,
                model='english' if request['language']=='en-IN' else 'multilingual')
        answer = result['answers']['route']
        print(json.dumps({'route':answer.get('choice'), 'confidence':answer.get('confidence'),
            'seconds':round(time.perf_counter()-started,3)}), flush=True)
except Exception as error:
    print(json.dumps({'error_type':type(error).__name__}), flush=True)
    raise SystemExit(1)
