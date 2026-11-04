from datetime import datetime
from pathlib import Path

import pytest

from scripts.exportar_pruebas_web import limpiar_junit, siguiente_id

JUNIT = """<?xml version="1.0" encoding="UTF-8" ?>
<testsuites name="vitest tests" tests="3" failures="{f}" errors="{e}" time="1">
  <testsuite name="src/a.spec.ts" hostname="EQUIPO-1" tests="2" failures="{f}" errors="{e}" skipped="0" time="0.5">
    <testcase classname="src/a.spec.ts" name="a" time="0.1"></testcase>
    <testcase classname="src/a.spec.ts" name="b" time="0.1"></testcase>
  </testsuite>
  <testsuite name="src/b.spec.ts" hostname="EQUIPO-1" tests="1" failures="0" errors="0" skipped="{s}" time="0.5">
    <testcase classname="src/b.spec.ts" name="c" time="0.1"></testcase>
  </testsuite>
</testsuites>
"""


def test_quita_el_hostname_y_resume(tmp_path):
    junit = tmp_path / "j.xml"
    junit.write_text(JUNIT.format(f=0, e=0, s=0), encoding="utf-8")
    assert limpiar_junit(junit) == {"superadas": 3, "fallidas": 0, "omitidas": 0, "archivos": 2}
    assert "hostname" not in junit.read_text(encoding="utf-8")


@pytest.mark.parametrize("f, e, s", [(1, 0, 0), (0, 1, 0), (0, 0, 1)])
def test_no_exporta_con_fallidas_errores_u_omitidas(tmp_path, f, e, s):
    junit = tmp_path / "j.xml"
    junit.write_text(JUNIT.format(f=f, e=e, s=s), encoding="utf-8")
    with pytest.raises(ValueError):
        limpiar_junit(junit)


def test_no_exporta_con_rutas_del_usuario(tmp_path):
    junit = tmp_path / "j.xml"
    junit.write_text(JUNIT.format(f=0, e=0, s=0).replace('name="c"', f'name="{Path.home().as_posix()}/x"'),
                     encoding="utf-8")
    with pytest.raises(ValueError):
        limpiar_junit(junit)


def test_siguiente_id_por_dia(tmp_path):
    fecha = datetime(2026, 11, 4)
    assert siguiente_id(tmp_path, fecha) == "interfaz-2026-11-04-01"
    (tmp_path / "interfaz-2026-11-04-01_pruebas.xml").touch()
    (tmp_path / "api-2026-11-04-07_pruebas.xml").touch()
    assert siguiente_id(tmp_path, fecha) == "interfaz-2026-11-04-02"
