import json

from app.services.label_extraction import Extraction, LabelExtractionError
from scripts import extract_label as cli


def test_prints_result_with_meta(tmp_path, monkeypatch, capsys):
    photo = tmp_path / "label.jpg"
    photo.write_bytes(b"jpg")
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    monkeypatch.setattr(
        cli,
        "extract_label_file",
        lambda path, config: Extraction({"status": "not_found"}, config.model, 1.234, 10, 20),
    )

    assert cli.main([str(photo)]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "not_found"
    assert output["meta"]["latency_seconds"] == 1.23
    assert (output["meta"]["input_tokens"], output["meta"]["output_tokens"]) == (10, 20)


def test_reports_errors_on_stderr(tmp_path, monkeypatch, capsys):
    photo = tmp_path / "label.jpg"
    photo.write_bytes(b"jpg")
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert cli.main([str(photo)]) == 1
    assert "GEMINI_API_KEY" in capsys.readouterr().err

    monkeypatch.setenv("GEMINI_API_KEY", "key")

    def fail(path, config):
        raise LabelExtractionError("HTTP 500: busy")

    monkeypatch.setattr(cli, "extract_label_file", fail)
    assert cli.main([str(photo)]) == 1
    assert "HTTP 500" in capsys.readouterr().err
