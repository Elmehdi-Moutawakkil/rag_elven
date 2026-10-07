from scripts.sanity_check import PROVIDER_API_KEY_ENVS
from src.settings import DEEPSEEK_API_KEY_ENV


def test_sanity_check_reports_deepseek_api_key_status():
    assert DEEPSEEK_API_KEY_ENV in PROVIDER_API_KEY_ENVS
