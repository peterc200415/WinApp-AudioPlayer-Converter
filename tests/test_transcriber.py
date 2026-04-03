from src.core import transcriber as transcriber_module


def build_transcriber():
    transcriber_module.Transcriber._instance = None
    return transcriber_module.Transcriber()


def test_load_model_falls_back_to_cpu_on_cuda_driver_error(monkeypatch):
    transcriber = build_transcriber()
    messages = []
    transcriber.on_info = messages.append

    cpu_model = object()
    load_calls = []

    def fake_load_model(model_name, device):
        load_calls.append((model_name, device))
        if device == "cuda":
            raise RuntimeError("CUDA driver version is insufficient for CUDA runtime version")
        return cpu_model

    emptied = []

    monkeypatch.setattr(transcriber, "_get_device", lambda _device: "cuda")
    monkeypatch.setattr(transcriber_module.whisper, "load_model", fake_load_model)
    monkeypatch.setattr(transcriber_module.torch.cuda, "empty_cache", lambda: emptied.append(True), raising=False)

    transcriber.load_model("base", "auto")

    assert load_calls == [("base", "cuda"), ("base", "cpu")]
    assert transcriber.device == "cpu"
    assert transcriber.model_name == "base"
    assert transcriber._model is cpu_model
    assert transcriber._disable_cuda is True
    assert emptied == [True]
    assert any("falling back to CPU" in message for message in messages)


def test_get_device_falls_back_to_cpu_when_cuda_probe_hits_driver_error(monkeypatch):
    transcriber = build_transcriber()
    messages = []
    transcriber.on_info = messages.append

    monkeypatch.setattr(transcriber_module.torch, "__version__", "2.5.1+cu121")
    monkeypatch.setattr(transcriber_module.torch.cuda, "is_available", lambda: True, raising=False)
    monkeypatch.setattr(
        transcriber_module.torch.cuda,
        "get_device_capability",
        lambda _index: (_ for _ in ()).throw(RuntimeError("Found no NVIDIA driver on your system")),
        raising=False,
    )

    device = transcriber._get_device("auto")

    assert device == "cpu"
    assert transcriber._disable_cuda is True
    assert any("CUDA probe failed" in message for message in messages)
