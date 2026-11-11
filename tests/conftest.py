import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_text():
    return lambda name: (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def fixture_json(fixture_text):
    return lambda name: json.loads(fixture_text(name))
