import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
PEXELS_KEY = os.getenv('PEXELS_API_KEY', '')
OUTPUT_DIR = Path(os.getenv('OUTPUT_DIR', './jobs')).resolve()
MAX_CLIPS = max(1, min(20, int(os.getenv('MAX_CLIPS', '8'))))
MAX_DURATION = max(5, min(600, int(os.getenv('MAX_DURATION_SECONDS', '90'))))
MAX_SOURCE_BYTES = int(os.getenv('MAX_SOURCE_MB', '70')) * 1024 * 1024
ALLOWED_USER_IDS = {int(x.strip()) for x in os.getenv('ALLOWED_USER_IDS', '').split(',') if x.strip().isdigit()}
# Backwards compatible: OPENAI_API_KEY stays the primary setting.
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY_PRIMARY') or os.getenv('OPENAI_API_KEY', '')
OPENAI_API_KEY_SECONDARY = os.getenv('OPENAI_API_KEY_SECONDARY', '')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY','')
OPENAI_MODEL = os.getenv('OPENAI_MODEL','gpt-4.1-mini')
GEMINI_MODEL = os.getenv('GEMINI_MODEL','gemini-2.5-flash')
MAX_UPLOAD_MB = int(os.getenv('MAX_UPLOAD_MB','19'))
MAX_USER_CLIPS = int(os.getenv('MAX_USER_CLIPS','20'))
VIDEO_PRESET = os.getenv('VIDEO_PRESET','veryfast')
MAX_DURATION = max(5,min(10800,int(os.getenv('MAX_DURATION_SECONDS','3600'))))
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL','').strip().rstrip('/')
DOWNLOAD_SECRET = os.getenv('DOWNLOAD_SECRET','').strip()
PUBLIC_HOST = os.getenv('PUBLIC_HOST','127.0.0.1')
PUBLIC_PORT = int(os.getenv('PUBLIC_PORT','8088'))

SCENE_DETECTION = os.getenv('SCENE_DETECTION','0').lower() in ('1','true','yes')
SILENCE_CLEANUP = os.getenv('SILENCE_CLEANUP','0').lower() in ('1','true','yes')
WHISPER_MODEL = os.getenv('WHISPER_MODEL','').strip()
