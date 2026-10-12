"""v3.1 settings. No credentials are stored in source code."""
import os
from pathlib import Path
APP_NAME = 'Simple Bank Orderly'
APP_VERSION = '3.1'
DATA_DIR = Path(os.getenv('BANK_DATA_DIR', str(Path(__file__).parent / 'data')))
BACKEND = os.getenv('BANK_BACKEND', 'mysql').lower()
DB_CONFIG = dict(host=os.getenv('BANK_DB_HOST', 'localhost'),
                 port=int(os.getenv('BANK_DB_PORT', '3306')),
                 user=os.getenv('BANK_DB_USER', 'bank_app'),
                 password=os.getenv('BANK_DB_PASSWORD', ''),
                 database=os.getenv('BANK_DB_NAME', 'simple_bank_v3'))
