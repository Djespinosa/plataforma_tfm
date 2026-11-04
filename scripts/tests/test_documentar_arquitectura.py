from datetime import datetime

import pytest

from scripts import documentar_arquitectura as doc


def test_cada_ruta_de_la_api_esta_documentada_con_su_requisito():
    registradas = doc.rutas_registradas()
    assert registradas == set(doc.RUTAS)
    texto = doc.endpoints_md(registradas)
    assert texto.count("\n| GET ") + texto.count("\n| POST ") == len(doc.RUTAS)
    assert all(linea.count("|") == 5 for linea in texto.splitlines() if linea.startswith("| "))


def test_una_ruta_nueva_o_borrada_impide_exportar():
    registradas = doc.rutas_registradas()
    with pytest.raises(ValueError):
        doc.endpoints_md(registradas | {("DELETE", "/api/conjuntos/<int:id_>")})
    with pytest.raises(ValueError):
        doc.endpoints_md(registradas - {("GET", "/api/estado")})


def test_modelo_de_datos_con_las_6_tablas_el_indice_parcial_y_los_3_disparadores(tmp_path):
    entradas = doc.exportar(tmp_path, "abc1234", datetime(2026, 11, 4))
    assert [e["archivo"] for e in entradas] == ["arquitectura/endpoints.md", "arquitectura/modelo_datos.md"]
    texto = (tmp_path / "arquitectura" / "modelo_datos.md").read_text(encoding="utf-8")
    assert texto.count("CREATE TABLE ") == 6
    assert "WHERE evaluacion_prueba IS NOT NULL" in texto
    assert texto.count("CREATE TRIGGER ") == 3
    assert not any(linea != linea.rstrip() for linea in texto.splitlines())
