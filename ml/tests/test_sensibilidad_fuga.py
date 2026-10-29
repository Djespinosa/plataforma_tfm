"""Pruebas de ml/sensibilidad_fuga.py (D20, D39, D38): filas comunes, descomposición de la inflación, bootstrap por
estudiante y figura; con OULAD, que cada población con fuga contiene a la principal y solo añade retirados."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

import sensibilidad_fuga as sf
from evidencias import EVIDENCIAS
from experimento import PROCESADO, cargar_cortes, cargar_entrenamiento


def poblaciones(n: int = 600, extra: int = 80, semilla: int = 0):
    """Población principal y con fuga (la principal más `extra` retirados, todos positivos y fáciles de detectar)."""
    rng = np.random.default_rng(semilla)
    # Cada estudiante tiene una matrícula en 2013B y otra en 2013J (claves únicas, estudiantes repetidos).
    principal = pd.DataFrame({"code_module": "AAA", "code_presentation": np.repeat(["2013B", "2013J"], n // 2),
                              "id_student": np.arange(n) % (n // 2), "etiqueta": rng.integers(0, 2, n)})
    principal["presentacion"] = "AAA_" + principal["code_presentation"]
    principal["pliegue"] = principal["code_presentation"].map({"2013B": 0, "2013J": 1})
    retirados = principal.sample(extra, random_state=semilla).assign(etiqueta=1, id_student=lambda d: d["id_student"] + n)
    fuga = pd.concat([principal, retirados]).sort_index(kind="stable").reset_index(drop=True)
    return principal.reset_index(drop=True), fuga


def test_filas_comunes_marca_la_principal_y_exige_orden_y_pliegues():
    principal, fuga = poblaciones()
    comun = sf.filas_comunes(fuga, principal)
    assert comun.sum() == len(principal) and fuga.loc[~comun, "etiqueta"].eq(1).all()
    with pytest.raises(ValueError, match="mismo orden"):
        sf.filas_comunes(fuga, principal.iloc[::-1].reset_index(drop=True))
    with pytest.raises(ValueError, match="más de un pliegue"):
        sf.filas_comunes(fuga.assign(pliegue=np.where(comun, fuga["pliegue"], 5)), principal)


def test_descomposicion_suma_y_coincide_con_roc_auc():
    principal, fuga = poblaciones()
    comun = sf.filas_comunes(fuga, principal)
    rng = np.random.default_rng(1)
    y = fuga["etiqueta"].to_numpy()
    p_fuga = np.where(comun, 0.3 * y + rng.random(len(y)), 2.0)  # los retirados, con la mayor probabilidad
    p_principal = 0.2 * principal["etiqueta"].to_numpy() + rng.random(len(principal))
    r = sf.descomposicion(fuga["id_student"].to_numpy(), y, p_fuga, comun, p_principal, 300, 42)
    assert r["roc_auc_fuga_su_poblacion"] == round(roc_auc_score(y, p_fuga), 4)
    assert r["roc_auc_fuga_comunes"] == round(roc_auc_score(y[comun], p_fuga[comun]), 4)
    assert r["roc_auc_principal"] == round(roc_auc_score(principal["etiqueta"], p_principal), 4)
    assert abs(r["inflacion"]["valor"] - r["efecto_evaluar"]["valor"] - r["efecto_entrenar"]["valor"]) <= 2e-4
    assert r["efecto_evaluar"]["valor"] > 0 and r["suma_comprobada"]
    for componente in sf.COMPONENTES:
        bajo, alto = r[componente]["ic95_bootstrap"]
        assert bajo <= r[componente]["valor"] <= alto
    assert "delong_p" in r["efecto_entrenar"]


def test_bootstrap_por_estudiante_mantiene_juntas_sus_matriculas_y_empareja_las_comunes():
    principal, fuga = poblaciones()
    comun = sf.filas_comunes(fuga, principal)
    y = fuga["etiqueta"].to_numpy()
    p = np.random.default_rng(2).random(len(y))
    m = sf.bootstrap_por_estudiante(fuga["id_student"].to_numpy(), y, p, comun, p[comun], 200, 42)
    assert len(m) == 200 and (m["fuga_comunes"] == m["principal"]).all()  # mismas filas comunes en cada réplica
    # Sin retirados añadidos, la población con fuga es la principal: el efecto de evaluar es 0 en todas las réplicas.
    todo = np.ones(len(principal), dtype=bool)
    m = sf.bootstrap_por_estudiante(principal["id_student"].to_numpy(), principal["etiqueta"].to_numpy(),
                                    p[comun], todo, p[comun], 50, 42)
    assert (m["fuga_poblacion"] == m["fuga_comunes"]).all()
    # Un estudiante con dos matrículas aporta las dos o ninguna: con un solo estudiante, todas las réplicas son iguales.
    m = sf.bootstrap_por_estudiante(np.zeros(4), np.array([0, 1, 0, 1]), np.array([0.1, 0.9, 0.2, 0.8]),
                                    np.ones(4, dtype=bool), np.array([0.1, 0.9, 0.2, 0.8]), 20, 42)
    assert m["fuga_poblacion"].eq(1.0).all()


def test_figura_con_eje_y_comun_y_los_tres_componentes(tmp_path, monkeypatch):
    capturadas = []
    monkeypatch.setattr(sf.plt, "close", capturadas.append)
    componente = lambda v: {"valor": v, "ic95_bootstrap": [v - 0.01, v + 0.01]}  # noqa: E731
    modelos = lambda d: [{"papel": papel, "modelo": modelo, "inflacion": componente(2 * d),  # noqa: E731
                          "efecto_evaluar": componente(d), "efecto_entrenar": componente(d)}
                         for papel, modelo in (("mejor_automl", "apilamiento"), ("rl_desplegada", "rl"))]
    sf.figura_inflacion([{"semana": s, "modelos": modelos(d)} for s, d in ((0, 0.01), (4, 0.05))],
                        tmp_path / "figura.png")
    ejes = capturadas[0].axes
    assert (tmp_path / "figura.png").exists() and ejes[0].get_ylim() == ejes[1].get_ylim()
    assert len(capturadas[0].legends[0].get_texts()) == len(sf.COMPONENTES)


def test_oulad_poblacion_con_fuga_contiene_a_la_principal_y_solo_anade_retirados():
    """En los 4 momentos, la población de D20 contiene a la principal (mismas filas, orden, pliegues y etiquetas) y lo
    único que añade son retirados (D39); la población crece con la semana."""
    if not (PROCESADO / f"semana_0{sf.SUFIJO}.parquet").exists():
        pytest.skip("Sin los cortes de OULAD en data/procesado/cortes")
    cortes, _ = cargar_cortes("exp-2026-10-23-02")
    anadidos = []
    for semana in (0, 4, 8, 12):
        principal = cargar_entrenamiento(semana, cortes)
        fuga = cargar_entrenamiento(semana, cortes, sf.SUFIJO)
        comun = sf.filas_comunes(fuga, principal)
        assert fuga.loc[~comun, "etiqueta"].eq(1).all() and (~comun).sum() > 0
        anadidos.append(int((~comun).sum()))
    assert anadidos == sorted(anadidos)
    assert (EVIDENCIAS / "experimentos" / "exp-2026-10-23-02.json").exists()
