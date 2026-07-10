from __future__ import annotations

import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
INTELLIGENCE=Path('/app') if Path('/app/config.py').exists() else ROOT/'intelligence'
DATABASE=Path('/database') if Path('/database/migrate.py').exists() else ROOT/'database'
sys.path.insert(0,str(INTELLIGENCE))
sys.path.insert(0,str(DATABASE))
