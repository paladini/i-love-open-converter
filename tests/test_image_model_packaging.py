from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx"
MODEL_SHA256 = "309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8"


def test_u2netp_model_is_verified_and_available_to_offline_worker():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    worker_compose = compose.split("\n  worker:\n", maxsplit=1)[1]

    assert MODEL_URL in dockerfile
    assert f"{MODEL_SHA256}  /opt/u2net/u2netp.onnx" in dockerfile
    assert "sha256sum -c -" in dockerfile
    assert "COPY --from=verapdf-installer /opt/u2net /opt/u2net" in dockerfile
    assert "U2NET_HOME=/opt/u2net" in dockerfile
    assert "network_mode: none" in worker_compose
