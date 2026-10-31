"""Salvaguardas de la exportación de pruebas a evidencias/ (api/exportar_pruebas.py, docs/diseno-api.md §10): nada se
exporta con pruebas omitidas o fallidas, sin el motor de las funcionales, con rutas absolutas ni con la contraseña."""

import json
from urllib.parse import quote_plus

import pytest

from api import exportar_pruebas


def junit(tmp_path, *, omitidas=0, fallos=0, motor=True):
    propiedades = '<properties><property name="motor_bd_funcionales" value="postgresql 16.15" /></properties>'
    caso = '<testcase name="a"><properties><property name="requisito" value="RF-01" /></properties></testcase>'
    ruta = tmp_path / "x_pruebas.xml"
    ruta.write_text(f'<testsuites><testsuite name="pytest" hostname="equipo" tests="2" skipped="{omitidas}" '
                    f'failures="{fallos}" errors="0">{propiedades if motor else ""}{caso}<testcase name="b" />'
                    '</testsuite></testsuites>', encoding="utf-8")
    return ruta


def test_junit_sin_hostname_y_resumen(tmp_path):
    ruta = junit(tmp_path)
    assert exportar_pruebas.limpiar_junit(ruta) == {
        "superadas": 2, "fallidas": 0, "omitidas": 0, "funcionales": 1, "motor_bd_funcionales": "postgresql 16.15",
        "funcionales_por_requisito": {"RF-01": 1}}
    assert "hostname" not in ruta.read_text(encoding="utf-8")


@pytest.mark.parametrize("cambios", [{"omitidas": 1}, {"fallos": 1}, {"motor": False}])
def test_junit_con_omitidas_fallidas_o_sin_motor_no_se_exporta(tmp_path, cambios):
    with pytest.raises(SystemExit):
        exportar_pruebas.limpiar_junit(junit(tmp_path, **cambios))


def test_cobertura_por_paquete_y_sin_rutas_absolutas(tmp_path):
    resumen = lambda n, c: {"summary": {"num_statements": n, "covered_lines": c}}  # noqa: E731
    ruta = tmp_path / "c.json"
    ruta.write_text(json.dumps({"files": {"api\\bd.py": resumen(10, 9), "ml/automl/motor.py": resumen(4, 2)}}))
    assert exportar_pruebas.resumir_cobertura(ruta) == {
        "api": {"archivos": 1, "lineas": 10, "cubiertas": 9, "porcentaje": 90.0},
        "ml/automl": {"archivos": 1, "lineas": 4, "cubiertas": 2, "porcentaje": 50.0}}
    ruta.write_text(json.dumps({"files": {str(tmp_path / "api" / "bd.py"): resumen(10, 9)}}))
    with pytest.raises(SystemExit):
        exportar_pruebas.resumir_cobertura(ruta)


def test_no_exporta_la_contrasena(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL_PRUEBAS", f"postgresql+psycopg://u:{quote_plus('a b/c')}@127.0.0.1:5433/p")
    limpio, sucio = tmp_path / "limpio.xml", tmp_path / "sucio.xml"
    limpio.write_text("<testsuite />", encoding="utf-8")
    sucio.write_text("conninfo password=a+b%2Fc", encoding="utf-8")
    exportar_pruebas.sin_contrasena(limpio)
    with pytest.raises(SystemExit):
        exportar_pruebas.sin_contrasena(limpio, sucio)
    sucio.write_text("conninfo password=a+b/c", encoding="utf-8")  # decodificada: «+» no es espacio en make_url
    with pytest.raises(SystemExit):
        exportar_pruebas.sin_contrasena(sucio)


def test_manifest_ausente_se_crea_vacio(tmp_path):
    assert exportar_pruebas.leer_manifest(tmp_path)["pruebas"] == []
