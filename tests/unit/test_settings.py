from core.config import Settings


def test_settings_defaults_are_local_dev_friendly() -> None:
    settings = Settings()

    assert settings.app_name == "AI Knowledge Platform API"
    assert settings.app_version == "0.1.0"
    assert settings.environment == "local"
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.service_name == "api"
