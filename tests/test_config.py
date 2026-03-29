from src.utils.config import Config


def test_config_defaults_include_runtime_keys(tmp_path):
    config_path = tmp_path / "settings.json"

    config = Config(str(config_path))

    assert config.get("whisper_model") == "base"
    assert config.get("subtitle_preview_model") == "base"
    assert config.get("auto_transcribe_on_play") is True
    assert config.get("supported_formats") == Config.DEFAULT_SUPPORTED_FORMATS


def test_config_persists_updates(tmp_path):
    config_path = tmp_path / "settings.json"

    config = Config(str(config_path))
    config.set("device", "cpu")
    config.set("subtitle_font_size", 18)
    config.save()

    reloaded = Config(str(config_path))
    assert reloaded.get("device") == "cpu"
    assert reloaded.get("subtitle_font_size") == 18
