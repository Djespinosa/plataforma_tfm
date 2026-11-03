import hashlib
import json
from datetime import datetime

import pytest

from scripts.registrar_capturas import clasificar, entradas, registrar


@pytest.fixture
def raiz(tmp_path):
    csv = tmp_path / "data" / "procesado" / "demo"
    csv.mkdir(parents=True)
    (csv / "semana_4_2014B.csv").write_bytes(b"a,b\n1,2\n")
    (csv / "entrenamiento_semana_4.csv").write_bytes(b"a,y\n1,0\n")
    return tmp_path


def test_una_entrada_por_captura_cambiada_con_experimento_y_csv(raiz):
    nuevas = entradas({"web-seguimiento.png", "web-prediccion-lista.png"}, raiz, "abc1234", "web-2026-11-04-01")
    assert [n["archivo"] for n in nuevas] == ["capturas/web-prediccion-lista.png", "capturas/web-seguimiento.png"]
    lista, seguimiento = nuevas
    assert lista["commit"] == "abc1234"
    assert lista["datos"]["experimento"] == "exp-2026-10-29-03"
    assert lista["datos"]["csv"] == {
        "ruta": "data/procesado/demo/semana_4_2014B.csv",
        "sha256": hashlib.sha256(b"a,b\n1,2\n").hexdigest()}
    assert seguimiento["datos"]["experimento"] == "web-2026-11-04-01"


def test_falta_el_experimento_web(raiz):
    with pytest.raises(ValueError, match="--experimento-web"):
        entradas({"web-carga.png"}, raiz, "abc1234", None)


def test_clasificar_solo_admite_capturas_de_la_lista_nuevas_o_cambiadas():
    status = "\n".join([
        " M evidencias/capturas/web-evaluacion-detalle.png",  # primera línea con espacio inicial
        "?? evidencias/capturas/web-carga.png",
        "M  evidencias/capturas/web-modelos.png",
        " D evidencias/capturas/web-seguimiento.png",
        " M web/src/app/textos.ts",
        "?? evidencias/capturas/notas.txt",
        "?? evidencias/capturas/web-otra.png",  # no está en CAPTURAS
        "?? evidencias/capturas/sub/web-carga.png",  # no está directamente en capturas/
    ])
    cambiadas, ajenas = clasificar(status)
    assert cambiadas == {"web-evaluacion-detalle.png", "web-carga.png", "web-modelos.png"}
    assert ajenas == [" D evidencias/capturas/web-seguimiento.png", " M web/src/app/textos.ts",
                      "?? evidencias/capturas/notas.txt", "?? evidencias/capturas/web-otra.png",
                      "?? evidencias/capturas/sub/web-carga.png"]
    assert clasificar("") == (set(), [])


def test_registrar_sustituye_las_del_mismo_archivo_y_conserva_el_resto(tmp_path):
    manifest = {"generado": "x", "commit": "viejo", "experimentos": ["e"], "figuras": [], "arquitectura": [],
                "pruebas": [], "usabilidad": [],
                "capturas": [{"archivo": "capturas/a.png"}, {"archivo": "capturas/web-modelos.png", "commit": "viejo"}]}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    nueva = {"archivo": "capturas/web-modelos.png", "descripcion": "d", "commit": "nuevo", "datos": {}}
    registrar(tmp_path, [nueva], "nuevo", datetime(2026, 11, 4, 10, 0))
    resultado = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert resultado["capturas"] == [{"archivo": "capturas/a.png"}, nueva]
    assert (resultado["commit"], resultado["generado"], resultado["experimentos"]) == ("nuevo", "2026-11-04T10:00:00",
                                                                                       ["e"])
