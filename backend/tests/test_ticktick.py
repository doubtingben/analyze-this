import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ticktick import TickTickClient


def test_ticktick_client_reads_env_at_instantiation(monkeypatch):
    monkeypatch.setenv("TICKTICK_ACCESS_TOKEN", "token-123")
    monkeypatch.setenv("TICKTICK_PROJECT_ID", "project-456")

    client = TickTickClient()

    assert client.access_token == "token-123"
    assert client.project_id == "project-456"
    assert client._check_config() is None


def test_ticktick_client_uses_explicit_args_over_env(monkeypatch):
    monkeypatch.setenv("TICKTICK_ACCESS_TOKEN", "env-token")
    monkeypatch.setenv("TICKTICK_PROJECT_ID", "env-project")

    client = TickTickClient(access_token="arg-token", project_id="arg-project")

    assert client.access_token == "arg-token"
    assert client.project_id == "arg-project"
