"""Project locations, resolved independently of the terminal's working directory."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = PROJECT_ROOT / 'assets'
MOTHER_ARTWORK_DIR = ASSETS_DIR / 'mother' / 'artwork'
MODELS_DIR = ASSETS_DIR / 'models'
SOUNDS_DIR = ASSETS_DIR / 'sounds'
CONFIG_DIR = PROJECT_ROOT / 'config'
DATA_DIR = PROJECT_ROOT / 'data'
KNOWN_FACES_DIR = DATA_DIR / 'known_faces'
RUNTIME_DIR = PROJECT_ROOT / 'runtime'
ENV_FILE = PROJECT_ROOT / '.env'
