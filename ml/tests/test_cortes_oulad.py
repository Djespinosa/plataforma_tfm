"""Pruebas anti-fuga de ml/cortes_oulad.py (punto 13 del encargo de la Entrega 2).

Datos sintéticos con casos límite elegidos a mano y, si están los CSV, una prueba de invariancia sobre OULAD real:
truncar las tablas al día del corte no debe cambiar ninguna variable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import cortes_oulad as co

PRESENTACIONES = ["2013J", "2014J"]
# id, final_result, date_registration, date_unregistration
ESTUDIANTES = [
    (1, "Pass", -30, np.nan),
    (2, "Withdrawn", -10, 40.0),
    (3, "Fail", np.nan, np.nan),     # sin fecha de matrícula: elegible
    (4, "Withdrawn", -20, -3.0),     # baja antes del día 0
    (5, "Pass", 35, np.nan),         # matrícula tardía
    (6, "Withdrawn", -5, 28.0),      # baja el mismo día del corte de la semana 4
    (7, "Withdrawn", -5, np.nan),    # D26
    (8, "Fail", -5, 100.0),          # D27
    (9, "Withdrawn", -5, 0.0),       # baja el día 0: fuera de la semana 0 principal, dentro de D20
]
CLICS = {  # id_student: [(día, id_site relativo, clics)]
    1: [(-5, 1, 2), (0, 1, 3), (10, 2, 4), (27, 3, 5), (28, 1, 6), (29, 1, 100), (40, 2, 7)],
    2: [(3, 1, 1), (20, 2, 2)],
    5: [(30, 1, 9)],
    6: [(1, 3, 8)],
}
# id_student: [(evaluación relativa, date_submitted, is_banked, score)]
ENTREGAS = {
    1: [(1, 18, 0, 80.0), (2, 22, 0, 70.0), (3, 45, 0, 60.0), (4, 250, 0, 90.0), (5, 25, 0, 75.0)],
    2: [(1, -1, 1, 55.0), (2, 30, 0, 65.0)],
    6: [(1, 15, 0, 40.0)],
}
# evaluación relativa: (tipo, fecha límite)
EVALUACIONES = {1: ("CMA", 20.0), 2: ("TMA", 20.0), 3: ("TMA", 50.0), 4: ("Exam", np.nan), 5: ("CMA", 60.0)}
TIPOS_SITIO = {1: "resource", 2: "quiz", 3: "forumng"}


def tablas_sinteticas() -> dict[str, pd.DataFrame]:
    info, registro, assessments, entregas, vle, clics = [], [], [], [], [], []
    for i, pres in enumerate(PRESENTACIONES):
        for est, resultado, alta, baja in ESTUDIANTES:
            info.append({"code_module": "AAA", "code_presentation": pres, "id_student": est,
                         "gender": "F" if est % 2 else "M", "region": "Wales", "highest_education": "HE Qualification",
                         "imd_band": "10-20" if est == 3 else "30-40%", "age_band": "0-35", "num_of_prev_attempts": 0,
                         "studied_credits": 60, "disability": "N", "final_result": resultado})
            registro.append({"code_module": "AAA", "code_presentation": pres, "id_student": est,
                             "date_registration": alta, "date_unregistration": baja})
        for ev, (tipo, fecha) in EVALUACIONES.items():
            assessments.append({"code_module": "AAA", "code_presentation": pres, "id_assessment": 10 * i + ev,
                                "assessment_type": tipo, "date": fecha, "weight": 10.0})
        for est, filas in ENTREGAS.items():
            entregas += [{"id_assessment": 10 * i + ev, "id_student": est, "date_submitted": d, "is_banked": b, "score": s}
                         for ev, d, b, s in filas]
        for sitio, tipo in TIPOS_SITIO.items():
            vle.append({"id_site": 10 * i + sitio, "code_module": "AAA", "code_presentation": pres,
                        "activity_type": tipo, "week_from": np.nan, "week_to": np.nan})
        filas_clics = dict(CLICS)
        if pres == co.PRESENTACION_PRUEBA:
            # Tipo de actividad solo presente en la prueba y actividad distinta de la de entrenamiento.
            vle.append({"id_site": 10 * i + 4, "code_module": "AAA", "code_presentation": pres,
                        "activity_type": "htmlactivity", "week_from": np.nan, "week_to": np.nan})
            filas_clics[3] = [(5, 4, 50), (6, 1, 30)]
        for est, filas in filas_clics.items():
            clics += [{"code_module": "AAA", "code_presentation": pres, "id_student": est, "id_site": 10 * i + s,
                       "date": d, "sum_click": c} for d, s, c in filas]
    return {
        "courses": pd.DataFrame({"code_module": "AAA", "code_presentation": PRESENTACIONES,
                                 "module_presentation_length": [260, 262]}),
        "studentInfo": pd.DataFrame(info),
        "studentRegistration": pd.DataFrame(registro),
        "assessments": pd.DataFrame(assessments),
        "studentAssessment": pd.DataFrame(entregas),
        "vle": pd.DataFrame(vle),
        "studentVle": pd.DataFrame(clics),
    }


def corte(tablas: dict[str, pd.DataFrame], semana: int, excluir_retirados: bool = True) -> pd.DataFrame:
    union = co.matriculas(tablas)
    pliegues = {p: 1 for p in union.loc[union["particion"] == "entrenamiento", "presentacion"].unique()}
    return co.construir_corte(union, pliegues, co.preparar_clics(tablas), co.preparar_entregas(tablas),
                              tablas["assessments"], co.tipos_actividad(tablas["vle"]), semana, excluir_retirados)


def perturbar_etiqueta_y_baja(tablas: dict[str, pd.DataFrame], dia: int) -> dict[str, pd.DataFrame]:
    """Retrasa 1000 días toda baja posterior al corte y rota final_result entre Pass, Distinction y Fail en las
    matrículas sin baja (no altera la etiqueta, la población del corte ni D26/D27)."""
    registro = tablas["studentRegistration"].copy()
    futura = registro["date_unregistration"] > dia
    registro.loc[futura, "date_unregistration"] += 1000
    info = tablas["studentInfo"].copy()
    sin_baja = info.merge(tablas["studentRegistration"], on=co.CLAVES, how="left")["date_unregistration"].isna()
    rotacion = {"Pass": "Distinction", "Distinction": "Fail", "Fail": "Pass"}
    info.loc[sin_baja, "final_result"] = info.loc[sin_baja, "final_result"].replace(rotacion)
    return dict(tablas, studentRegistration=registro, studentInfo=info)


def truncar(tablas: dict[str, pd.DataFrame], dia: int) -> dict[str, pd.DataFrame]:
    """Elimina todo registro con fecha posterior al corte en las tablas que tienen fecha de evento."""
    truncadas = dict(tablas)
    truncadas["studentVle"] = tablas["studentVle"][tablas["studentVle"]["date"] <= dia]
    truncadas["studentAssessment"] = tablas["studentAssessment"][tablas["studentAssessment"]["date_submitted"] <= dia]
    return truncadas


def fila(df: pd.DataFrame, est: int, pres: str = "2013J") -> pd.Series:
    return df[(df["id_student"] == est) & (df["code_presentation"] == pres)].iloc[0]


# --- Población ---------------------------------------------------------------------------------------------------

def test_eliminaciones_d26_d27():
    base = co.poblacion_base(co.matriculas(tablas_sinteticas()))
    assert not base["id_student"].isin([7, 8]).any()


def test_etiqueta_d2():
    datos = corte(tablas_sinteticas(), 0)
    final = datos.merge(tablas_sinteticas()["studentInfo"], on=co.CLAVES)["final_result"]
    assert (datos["etiqueta"] == (final == "Withdrawn").astype(int)).all()
    assert datos["etiqueta"].sum() > 0


@pytest.mark.parametrize("semana, esperados", [(0, {1, 2, 3, 6}), (4, {1, 2, 3}), (8, {1, 3, 5}), (12, {1, 3, 5})])
def test_poblacion_por_corte(semana, esperados):
    datos = corte(tablas_sinteticas(), semana)
    for pres in PRESENTACIONES:
        assert set(datos.loc[datos["code_presentation"] == pres, "id_student"]) == esperados


@pytest.mark.parametrize("semana", co.SEMANAS)
def test_ninguna_matricula_dada_de_baja_ni_tardia(semana):
    tablas = tablas_sinteticas()
    datos = corte(tablas, semana).merge(tablas["studentRegistration"], on=co.CLAVES, suffixes=("", "_original"))
    dia = 7 * semana
    assert not (datos["date_unregistration"] <= dia).any()
    assert not (datos["date_registration_original"] > dia).any()


@pytest.mark.parametrize("semana, esperados", [
    (0, {1, 2, 3, 6, 9}), (4, {1, 2, 3, 6, 9}),     # 5 sigue siendo tardía; 9 (baja el día 0) se conserva
    (8, {1, 2, 3, 5, 6, 9}), (12, {1, 2, 3, 5, 6, 9}),
])
def test_d20_solo_excluye_bajas_antes_del_inicio(semana, esperados):
    datos = corte(tablas_sinteticas(), semana, excluir_retirados=False)
    for pres in PRESENTACIONES:
        assert set(datos.loc[datos["code_presentation"] == pres, "id_student"]) == esperados


# --- Invariancia ante información posterior al corte -------------------------------------------------------------

@pytest.mark.parametrize("semana", co.SEMANAS)
@pytest.mark.parametrize("excluir_retirados", [True, False])
def test_truncar_al_corte_no_cambia_nada(semana, excluir_retirados):
    tablas = tablas_sinteticas()
    pd.testing.assert_frame_equal(
        corte(tablas, semana, excluir_retirados), corte(truncar(tablas, 7 * semana), semana, excluir_retirados)
    )


@pytest.mark.parametrize("semana", co.SEMANAS)
@pytest.mark.parametrize("excluir_retirados", [True, False])
def test_variables_no_dependen_de_la_etiqueta_ni_de_la_baja_futura(semana, excluir_retirados):
    tablas = tablas_sinteticas()
    pd.testing.assert_frame_equal(
        corte(tablas, semana, excluir_retirados),
        corte(perturbar_etiqueta_y_baja(tablas, 7 * semana), semana, excluir_retirados),
    )


def test_tipos_de_actividad_solo_de_entrenamiento():
    tablas = tablas_sinteticas()
    assert co.tipos_actividad(tablas["vle"]) == ["forumng", "quiz", "resource"]
    datos = corte(tablas, 4)
    assert "clics_htmlactivity" not in datos.columns
    assert fila(datos, 3, co.PRESENTACION_PRUEBA)["clics_total"] == 80  # sus clics cuentan en el total


def test_percentil_de_cohorte_exacto_y_por_presentacion():
    """Cohorte de 2013J en la semana 4: 1, 2, 3 y las matrículas 7 y 8 (que D26/D27 eliminan después, pero que
    en despliegue estarían). Clics: 1 → 20, 2 → 3, 3, 7 y 8 → 0 (empate: rango medio 2 de 5)."""
    datos = corte(tablas_sinteticas(), 4)
    percentiles = {e: fila(datos, e)["percentil_clics_total_cohorte"] for e in (1, 2, 3)}
    assert percentiles == pytest.approx({1: 1.0, 2: 0.8, 3: 0.4})
    assert fila(datos, 3, co.PRESENTACION_PRUEBA)["percentil_clics_total_cohorte"] == pytest.approx(1.0)


def test_actividad_de_la_prueba_no_cambia_las_filas_de_entrenamiento():
    tablas = tablas_sinteticas()
    vle_clics = tablas["studentVle"]
    de_prueba = vle_clics["code_presentation"] == co.PRESENTACION_PRUEBA
    modificadas = dict(tablas, studentVle=vle_clics.assign(sum_click=np.where(de_prueba, vle_clics["sum_click"] * 37 + 5,
                                                                                vle_clics["sum_click"])))
    for semana in co.SEMANAS:
        antes, despues = corte(tablas, semana), corte(modificadas, semana)
        entrenamiento = antes["particion"] == "entrenamiento"
        pd.testing.assert_frame_equal(antes[entrenamiento], despues[despues["particion"] == "entrenamiento"])


def test_clic_posterior_de_otro_estudiante_no_cambia_la_cohorte():
    tablas = tablas_sinteticas()
    extra = tablas["studentVle"].iloc[[0]].assign(id_student=3, date=29, sum_click=10_000)
    modificadas = dict(tablas, studentVle=pd.concat([tablas["studentVle"], extra], ignore_index=True))
    pd.testing.assert_frame_equal(corte(tablas, 4), corte(modificadas, 4))


@pytest.mark.parametrize("semana", co.SEMANAS)
def test_notas_de_tma_no_se_usan(semana):
    tablas = tablas_sinteticas()
    sa = tablas["studentAssessment"].merge(tablas["assessments"][["id_assessment", "assessment_type"]])
    otras = sa.assign(score=np.where((sa["assessment_type"] == "TMA") & (sa["is_banked"] == 0), 1.0, sa["score"]))
    modificadas = dict(tablas, studentAssessment=otras.drop(columns="assessment_type"))
    pd.testing.assert_frame_equal(corte(tablas, semana), corte(modificadas, semana))


@pytest.mark.parametrize("semana", co.SEMANAS)
def test_examenes_excluidos_aunque_se_entreguen_antes_del_corte(semana):
    tablas = tablas_sinteticas()
    examenes = tablas["assessments"].loc[tablas["assessments"]["assessment_type"] == "Exam", "id_assessment"]
    sa = tablas["studentAssessment"].copy()
    es_examen = sa["id_assessment"].isin(examenes)
    sa.loc[es_examen, ["date_submitted", "score"]] = [0, 1.0]
    pd.testing.assert_frame_equal(corte(tablas, semana), corte(dict(tablas, studentAssessment=sa), semana))


# --- Valores esperados ---------------------------------------------------------------------------------------------

def test_variables_de_evaluaciones_semana_4():
    datos = corte(tablas_sinteticas(), 4)
    uno = fila(datos, 1)
    assert uno["n_evaluaciones_vencidas"] == 2          # CMA y TMA con fecha límite 20; TMA 50 y CMA 60 aún no
    assert uno["n_entregadas"] == 2                     # la CMA 60 entregada el día 25 no cuenta como entrega
    assert uno["n_entregas_tardias"] == 1               # TMA entregada el día 22
    assert uno["antelacion_media"] == pytest.approx((2 + -2) / 2)
    assert uno["n_cma_calificadas"] == 2                # CMA 18 y CMA entregada el día 25
    assert uno["nota_media_cma"] == pytest.approx(77.5)  # sin la nota de la TMA (70) ni del examen (90)
    dos = fila(datos, 2)
    assert dos["n_evaluaciones_vencidas"] == 1          # la CMA convalidada no cuenta como pendiente
    assert dos["n_entregadas"] == 0                     # TMA entregada el día 30 > 28
    assert dos["proporcion_entregadas"] == 0
    assert np.isnan(dos["nota_media_cma"])              # la convalidada no alimenta las notas CMA
    assert dos["n_convalidadas"] == 1 and dos["nota_media_convalidada"] == 55


def test_convalidadas_solo_alimentan_sus_variables():
    """Una fila is_banked solo cambia sus variables propias y saca su evaluación del denominador de entregas."""
    tablas = tablas_sinteticas()
    extra = pd.DataFrame([{"id_assessment": 3, "id_student": 3, "date_submitted": -1, "is_banked": 1, "score": 50.0}])
    modificadas = dict(tablas, studentAssessment=pd.concat([tablas["studentAssessment"], extra], ignore_index=True))
    for semana, propias in ((4, {"n_convalidadas", "nota_media_convalidada"}),
                            (8, {"n_convalidadas", "nota_media_convalidada", "n_evaluaciones_vencidas"})):
        antes, despues = fila(corte(tablas, semana), 3), fila(corte(modificadas, semana), 3)
        distintas = {c for c in antes.index if not (antes[c] == despues[c] or (pd.isna(antes[c]) and pd.isna(despues[c])))}
        assert distintas == propias, semana


def test_variables_de_aula_virtual_semana_4():
    datos = corte(tablas_sinteticas(), 4)
    uno = fila(datos, 1)
    assert uno["clics_total"] == 2 + 3 + 4 + 5 + 6      # sin los clics de los días 29 y 40
    assert uno["dias_activos"] == 5
    assert uno["clics_resource"] == 2 + 3 + 6
    assert uno["clics_ventana_1"] == 5 + 6              # días 22-28
    assert uno["clics_ventana_3"] == 4                  # días (7, 14]
    assert uno["clics_ventana_4"] == 0                  # días (0, 7]: los clics de los días -5 y 0 quedan fuera
    assert uno["dias_desde_ultima_actividad"] == 0
    tres = fila(datos, 3)
    assert tres["sin_actividad"] == 1 and np.isnan(tres["dias_desde_ultima_actividad"])
    assert tres["percentil_clics_total_cohorte"] < uno["percentil_clics_total_cohorte"]


def test_columnas_coinciden_con_el_catalogo():
    tablas = tablas_sinteticas()
    catalogo = co.catalogo_variables(co.tipos_actividad(tablas["vle"]))
    variables = set(catalogo.loc[catalogo["motivo_exclusion"] == "", "nombre"])
    assert set(corte(tablas, 4).columns) - set(co.NO_VARIABLES) == variables
    assert not variables & {"date_unregistration", "final_result"}


def test_pliegues_tres_presentaciones_por_pliegue_y_reproducibles():
    presentaciones = [f"M{i:02d}_2013J" for i in range(15)] + ["M00_2014J"]
    base = pd.DataFrame({"presentacion": presentaciones,
                         "particion": ["entrenamiento"] * 15 + ["prueba"]})
    pliegues = co.asignar_pliegues(base)
    assert pliegues == co.asignar_pliegues(base)
    assert "M00_2014J" not in pliegues
    assert sorted(pd.Series(pliegues).value_counts()) == [3] * 5


# --- Datos reales ------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tablas_reales():
    if not (co.DATOS / "studentVle.csv").exists():
        pytest.skip("Sin los CSV de OULAD en data/raw/oulad")
    return co.cargar_tablas()


@pytest.mark.parametrize("semana", co.SEMANAS)
def test_oulad_real_invariante_al_truncar(tablas_reales, semana):
    completo = corte(tablas_reales, semana)
    pd.testing.assert_frame_equal(completo, corte(truncar(tablas_reales, 7 * semana), semana))
    pd.testing.assert_frame_equal(completo, corte(perturbar_etiqueta_y_baja(tablas_reales, 7 * semana), semana))
    datos = completo.merge(tablas_reales["studentRegistration"], on=co.CLAVES, suffixes=("", "_original"))
    assert not (datos["date_unregistration"] <= 7 * semana).any()
    assert not (datos["date_registration_original"] > 7 * semana).any()
    assert "clics_htmlactivity" not in completo.columns  # tipo que solo existe en 2014J
