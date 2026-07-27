from pathlib import Path

from trade_pipeline.api.settings import ApiEnvSettings, load_api_settings


def test_defaults(monkeypatch):
    for var in ("JWT_PRIVATE_KEY_PATH", "JWT_PUBLIC_KEY_PATH", "CORS_ORIGINS"):
        monkeypatch.delenv(var, raising=False)

    settings = ApiEnvSettings()

    assert settings.jwt_private_key_path.name == "private.pem"
    assert settings.jwt_public_key_path.name == "public.pem"
    assert settings.cors_origins_tuple == ("http://localhost:3000",)


def test_cors_origins_parses_comma_separated_list(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example.com, https://b.example.com")
    settings = ApiEnvSettings()
    assert settings.cors_origins_tuple == ("https://a.example.com", "https://b.example.com")


def test_env_var_overrides_key_path(monkeypatch, tmp_path):
    monkeypatch.setenv("JWT_PRIVATE_KEY_PATH", str(tmp_path / "custom_private.pem"))
    settings = ApiEnvSettings()
    assert settings.jwt_private_key_path == tmp_path / "custom_private.pem"


def test_load_api_settings_reads_real_key_files(tmp_path, monkeypatch):
    private_path = tmp_path / "private.pem"
    public_path = tmp_path / "public.pem"
    private_path.write_text("PRIVATE-CONTENT")
    public_path.write_text("PUBLIC-CONTENT")

    monkeypatch.setenv("JWT_PRIVATE_KEY_PATH", str(private_path))
    monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", str(public_path))
    monkeypatch.setenv("CORS_ORIGINS", "http://example.com")

    settings = load_api_settings()

    assert settings.private_key == "PRIVATE-CONTENT"
    assert settings.public_key == "PUBLIC-CONTENT"
    assert settings.cors_origins == ("http://example.com",)


def test_default_keys_dir_points_at_repo_keys_folder():
    from trade_pipeline.api.settings import DEFAULT_KEYS_DIR

    assert isinstance(DEFAULT_KEYS_DIR, Path)
    assert DEFAULT_KEYS_DIR.name == "keys"
