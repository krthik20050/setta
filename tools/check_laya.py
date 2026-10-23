"""Fail-fast Laya health check for the project environment."""
import json
import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
python = root / '.tools' / 'laya-env' / 'Scripts' / 'python.exe'
if not python.is_file():
    raise SystemExit('Laya environment is missing')
environment = {key: value for key, value in os.environ.items()
               if not any(secret in key.upper() for secret in ('TOKEN', 'SECRET', 'PASSWORD', 'API_KEY'))}
environment['HF_HOME'] = str(root / '.tools' / 'laya-model-cache')
environment['HF_HUB_OFFLINE'] = '1'
environment['PYTHONIOENCODING'] = 'utf-8'
request = json.dumps({'text': 'Play some relaxing music', 'language': 'en-IN'}) + '\n'
completed = subprocess.run(
    [str(python), str(root / 'tools' / 'laya_worker.py')],
    input=request, capture_output=True, text=True, encoding='utf-8',
    env=environment, timeout=180,
)
if completed.returncode:
    raise SystemExit(completed.stderr.strip() or 'Laya worker failed')
result = json.loads(completed.stdout.strip().splitlines()[-1])
if not result.get('route') or result.get('error_type'):
    raise SystemExit('Laya returned an invalid decision: '+json.dumps(result))
print(json.dumps(result, ensure_ascii=True))
