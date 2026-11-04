import json
from datetime import datetime

from scripts.diagrama_arquitectura import NOMBRE, exportar


def test_escribe_png_y_svg_y_los_registra_sin_duplicar_ni_tocar_otras_secciones(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps(
        {"generado": "x", "commit": "old", "capturas": [{"archivo": "capturas/a.png"}],
         "arquitectura": [{"archivo": f"arquitectura/{NOMBRE}.png", "commit": "old"}]}), encoding="utf-8")
    exportar(tmp_path, "abc1234", datetime(2026, 11, 3, 12))
    exportar(tmp_path, "def5678", datetime(2026, 11, 3, 13))

    png, svg = (tmp_path / "arquitectura" / f"{NOMBRE}.{ext}" for ext in ("png", "svg"))
    assert png.read_bytes().startswith(b"\x89PNG")
    assert "<svg" in svg.read_text(encoding="utf-8")
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert [(e["archivo"], e["commit"]) for e in manifest["arquitectura"]] == [
        (f"arquitectura/{NOMBRE}.png", "def5678"), (f"arquitectura/{NOMBRE}.svg", "def5678")]
    assert all(e["fuente"] == "scripts/diagrama_arquitectura.py" for e in manifest["arquitectura"])
    assert manifest["capturas"] == [{"archivo": "capturas/a.png"}]
    assert manifest["commit"] == "def5678"
