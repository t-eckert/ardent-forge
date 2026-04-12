import os
from unittest.mock import patch

from forge.config import Settings


def test_notebook_dir_default():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("FORGE_NOTEBOOK_DIR", None)
        settings = Settings()
        assert settings.notebook_dir == "/data/ardent-forge/notebook"


def test_notebook_dir_env_override():
    with patch.dict(os.environ, {"FORGE_NOTEBOOK_DIR": "/tmp/my-vault"}):
        settings = Settings()
        assert settings.notebook_dir == "/tmp/my-vault"
