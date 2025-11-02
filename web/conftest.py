# Asegura que 'orders' (dentro de web/apps) sea importable antes de colección
import sys
import pytest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent  # .../web
APPS_DIR = BASE_DIR / "apps"
p = str(APPS_DIR)
if p not in sys.path:
    sys.path.insert(0, p)

@pytest.fixture(autouse=True)
def use_stubs_for_tests(settings):
    settings.USE_HTTP_ADAPTERS = False