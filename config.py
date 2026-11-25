import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INSTANCE = ROOT / 'instance'
INSTANCE.mkdir(exist_ok=True)
DATABASE = os.environ.get('NUMART_DATABASE', str(INSTANCE / 'bookshop.db'))
SECRET_KEY = os.environ.get('NUMART_SECRET_KEY', 'local-development-only-change-this-before-sharing')
