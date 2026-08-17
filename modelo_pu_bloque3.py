# -*- coding: utf-8 -*-
"""
Bloque III del TFM — Modelo de aprendizaje automático (Positive-Unlabeled + SHAP)
================================================================================
Re-entrena el modelo PU usando las CINCO variables del AHP (C1-C5) en lugar de
las dos distancias del borrador anterior, elimina el filtro IQR (el control de
calidad de outliers pasa al apartado 4.7 de la memoria) y calcula la importancia
SHAP promediada sobre los 100 modelos del ensemble.

Salidas (carpeta ./salidas_bloque3):
  - boxplots_5variables.png        -> figura del apartado 4.7 (control de outliers)
  - distribucion_pu_score.png      -> figura 6.X (distribución del PU score)
  - shap_importancia_media.png     -> figura 6.X (importancia SHAP media, comparable al AHP)
  - ranking_top10.csv / .png       -> tabla 6.X (top 10 estaciones candidatas)
  - scores_pu_todas.csv            -> PU score de todas las no etiquetadas
  - comparacion_shap_ahp.csv       -> tabla de contraste SHAP vs pesos AHP
  - resumen_consola.txt            -> log reproducible de la ejecución

--------------------------------------------------------------------------------
CAMBIOS SOBRE LA VERSIÓN ORIGINAL DEL TUTOR (todos marcados con "# [FIX n]"):

  1. Capa de entrada: EESS_aragon_25830_PU en vez de EESS_aragon_25830.
     La capa original no tiene campo de etiqueta positiva (el script se detenía
     en sys.exit). La nueva la genera tfm_04_etiqueta_y_c1_corregido.py.

  2. C1 sin fuga de etiqueta: se usa C1_corr_n en lugar de C1_n. El C1 original
     mide la distancia al cargador más cercano SIN excluir el co-ubicado, por lo
     que valía ~0 en todas las positivas (media 41,7 m frente a 6.124 m en las
     no etiquetadas): el modelo aprendía la propia definición de la etiqueta y
     la importancia SHAP de C1 salía inflada y circular.

  3. arcpy pasa a ser opcional: si no está, la GDB se lee con geopandas/pyogrio
     (driver OpenFileGDB). Así el script corre fuera de ArcGIS Pro.

  4. boxplot(labels=...) -> boxplot(tick_labels=...): 'labels' se eliminó en
     matplotlib 3.11 y lanzaba TypeError.

  5. Identificador del ranking: 'Rotulo' no es único (222 valores distintos para
     518 estaciones; REPSOL aparece 138 veces). Se combina OBJECTID + rótulo +
     municipio/dirección para poder localizar cada estación.

  6. Hiperparámetros del Gradient Boosting: se fijan los mismos del borrador
     (n_estimators=150, learning_rate=0.04, max_depth=2, min_samples_leaf=10,
     subsample=0.8). La versión original usaba los defaults de sklearn
     (max_depth=3, lr=0.1), que no son comparables con lo publicado antes.

  7. Normalización de respaldo (solo si se usan las variables crudas): C4 y C5
     se invierten, como en la capa original (corr(C4_dist, C4_n) = -1,000 y
     corr(C5_nub, C5_n) = -1,000): menos distancia a núcleos y menos nubosidad
     son mejores. La versión original las normalizaba en sentido directo.
--------------------------------------------------------------------------------

Uso:
    python modelo_pu_bloque3.py
"""

import os
import sys
import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------
# 0. CONFIGURACIÓN  (única zona con rutas)
# ----------------------------------------------------------------------------
GDB          = r"E:\Clase\TFM\GasolinerasTFM\GasolinerasTFM.gdb"
CAPA_EESS    = "EESS_aragon_25830_PU"   # [FIX 1] capa con etiqueta y C1 corregido
SALIDAS      = os.path.join(os.getcwd(), "salidas_bloque3")

# Campos de las CINCO variables. El script prueba primero los normalizados
# y, si no existen, usa los crudos.
# [FIX 2] C1_corr_n (sin fuga) en lugar de C1_n.
CAMPOS_NORM  = ["C1_corr_n", "C2_n", "C3_n", "C4_n", "C5_n"]
CAMPOS_NORM_FALLBACK = ["C1_n", "C2_n", "C3_n", "C4_n", "C5_n"]
CAMPOS_CRUDO = ["C1_corr_dist", "C2_imd", "C3_pob", "C4_dist", "C5_nub"]

# Etiquetas legibles de cada variable (para figuras y tablas)
ETIQUETAS = {
    "C1": "C1 · Distancia a recarga rápida",
    "C2": "C2 · Afluencia de tráfico (IMD)",
    "C3": "C3 · Población (radio 10 km)",
    "C4": "C4 · Accesibilidad a núcleos",
    "C5": "C5 · Recurso solar (nubosidad)",
}
# Pesos del AHP (para el contraste final)
PESOS_AHP = {"C1": 26.3, "C2": 41.7, "C3": 9.7, "C4": 16.0, "C5": 6.2}

# Variables que se invierten al normalizar desde crudo ([FIX 7]).
INVERTIR_AL_NORMALIZAR = {"C4", "C5"}
# Variables con transformación log(1+x) antes del min-max.
LOG_AL_NORMALIZAR = {"C2", "C3"}

# Definición de "positiva": co-ubicada (<100 m) con recarga >= 50 kW.
CAMPO_POSITIVA_POSIBLES = ["Has_fast_charger", "TIENE_CARGADOR", "POSITIVA",
                           "has_charger", "cargador", "CARGADOR_50"]

# Hiperparámetros del PU ([FIX 6]: los mismos del borrador)
N_MODELOS      = 100     # tamaño del ensemble
RATIO_UNL_POS  = 1.5     # nº de no etiquetadas por cada positiva en cada iteración
SEMILLA        = 42
GB_PARAMS = dict(
    n_estimators=150,
    learning_rate=0.04,
    max_depth=2,
    min_samples_leaf=10,
    subsample=0.8,
)

os.makedirs(SALIDAS, exist_ok=True)
LOG = []
def log(msg=""):
    print(msg)
    LOG.append(str(msg))

# ----------------------------------------------------------------------------
# 1. CARGA DE DATOS DESDE LA GDB — arcpy si está, geopandas si no ([FIX 3])
# ----------------------------------------------------------------------------
def _leer_capa():
    """Devuelve (DataFrame, lista de campos) leyendo con arcpy o con geopandas."""
    try:
        import arcpy
        fc = os.path.join(GDB, CAPA_EESS)
        if not arcpy.Exists(fc):
            log(f"ERROR: no encuentro la capa {fc}")
            log("Revisa GDB y CAPA_EESS en la sección CONFIGURACIÓN.")
            sys.exit(1)
        campos = [f.name for f in arcpy.ListFields(fc)]
        filas = [list(r) for r in arcpy.da.SearchCursor(fc, campos)]
        log("Lectura de la GDB con arcpy.")
        return pd.DataFrame(filas, columns=campos), campos
    except ImportError:
        pass

    try:
        import geopandas as gpd
    except ImportError:
        log("ERROR: no hay ni arcpy ni geopandas para leer la GDB.")
        log("Instala geopandas o ejecuta con el Python de ArcGIS Pro.")
        sys.exit(1)

    try:
        gdf = gpd.read_file(GDB, layer=CAPA_EESS)
    except Exception as e:
        log(f"ERROR: no puedo leer {CAPA_EESS} de {GDB}: {e}")
        sys.exit(1)

    log("Lectura de la GDB con geopandas/pyogrio (arcpy no disponible).")
    df = pd.DataFrame(gdf.drop(columns=gdf.geometry.name))
    # OBJECTID no viaja en el DataFrame de geopandas: se reconstruye 1..n.
    if "OBJECTID" not in df.columns:
        df.insert(0, "OBJECTID", range(1, len(df) + 1))
    return df, list(df.columns)


def cargar_datos():
    df, campos_capa = _leer_capa()

    if all(c in campos_capa for c in CAMPOS_NORM):
        campos_x = CAMPOS_NORM
        normalizar_aqui = False
        log(f"Usando variables normalizadas de la capa: {campos_x}")
    elif all(c in campos_capa for c in CAMPOS_NORM_FALLBACK):
        campos_x = CAMPOS_NORM_FALLBACK
        normalizar_aqui = False
        log("AVISO: no encuentro C1_corr_n (C1 sin fuga de etiqueta); uso C1_n.")
        log("       La importancia SHAP de C1 saldrá inflada. Ejecuta antes")
        log("       tfm_04_etiqueta_y_c1_corregido.py para generar C1_corr_n.")
    elif all(c in campos_capa for c in CAMPOS_CRUDO):
        campos_x = CAMPOS_CRUDO
        normalizar_aqui = True
        log(f"Variables normalizadas no encontradas; uso crudas y normalizo aquí: {campos_x}")
    else:
        log("ERROR: no encuentro ni las 5 variables normalizadas ni las 5 crudas.")
        log(f"Campos disponibles: {campos_capa}")
        sys.exit(1)

    campo_pos = next((c for c in CAMPO_POSITIVA_POSIBLES if c in campos_capa), None)

    # [FIX 5] identificador compuesto: OBJECTID + rótulo + municipio/dirección
    campos_id = [c for c in ["OBJECTID", "Rotulo", "Direccion", "Provincia"]
                 if c in campos_capa]

    return df, campos_x, normalizar_aqui, campo_pos, campos_id


# ----------------------------------------------------------------------------
# 2. PREPARACIÓN: mapear a C1..C5, normalizar si hace falta, etiqueta PU
# ----------------------------------------------------------------------------
def preparar(df, campos_x, normalizar_aqui, campo_pos, campos_id):
    ren = {campos_x[i]: f"C{i+1}" for i in range(5)}
    df = df.rename(columns=ren)
    cols = ["C1", "C2", "C3", "C4", "C5"]

    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    n0 = len(df)
    df = df.dropna(subset=cols).reset_index(drop=True)
    if len(df) < n0:
        log(f"Aviso: {n0-len(df)} estaciones sin las 5 variables completas se descartan "
            f"(no es filtro de outliers, solo datos ausentes).")

    if normalizar_aqui:
        tmp = df.copy()
        for c in LOG_AL_NORMALIZAR:
            tmp[c] = np.log1p(tmp[c])
        for c in cols:
            lo, hi = tmp[c].min(), tmp[c].max()
            if hi == lo:
                df[c] = 0.0
            else:
                escalado = (tmp[c] - lo) / (hi - lo)
                # [FIX 7] C4 y C5 se invierten, como en la capa original.
                df[c] = 1.0 - escalado if c in INVERTIR_AL_NORMALIZAR else escalado
        log("Normalización aplicada: log(1+x) en C2 y C3, min-max 0-1 en las cinco, "
            "e inversión en C4 y C5 (menos distancia y menos nubosidad = mejor).")

    # [FIX 5] identificador legible y único para el ranking
    partes = []
    if "OBJECTID" in df.columns:
        partes.append(df["OBJECTID"].astype(str).str.zfill(3))
    if "Rotulo" in df.columns:
        partes.append(df["Rotulo"].fillna("").astype(str).str.strip())
    df["Estacion_id"] = partes[0] if len(partes) == 1 else partes[0] + " · " + partes[1]
    df["Ubicacion"] = (
        df["Direccion"].fillna("").astype(str).str.strip()
        if "Direccion" in df.columns else ""
    )

    if campo_pos:
        df["y"] = pd.to_numeric(df[campo_pos], errors="coerce").fillna(0).astype(int)
        df["y"] = (df["y"] > 0).astype(int)
        log(f"Etiqueta positiva tomada del campo '{campo_pos}' de la capa.")
    else:
        log("ATENCIÓN: no hay campo de positiva en la capa.")
        log("El script NO puede inventar qué estaciones tienen cargador.")
        log("Ejecuta antes tfm_04_etiqueta_y_c1_corregido.py, que genera la capa")
        log("EESS_aragon_25830_PU con el campo Has_fast_charger.")
        sys.exit(1)

    n_pos = int(df["y"].sum())
    log(f"Dataset: {len(df)} estaciones · {n_pos} positivas "
        f"({100*n_pos/len(df):.1f} %) · {len(df)-n_pos} no etiquetadas.")
    return df, cols


# ----------------------------------------------------------------------------
# 3. FIGURA 4.7 — boxplots de las 5 variables (control de outliers)
# ----------------------------------------------------------------------------
def figura_boxplots(df, cols):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 5))
    datos = [df[c].values for c in cols]
    etiq = [ETIQUETAS[c].replace(" · ", "\n") for c in cols]
    # [FIX 4] 'labels' se eliminó en matplotlib 3.11; el nombre actual es 'tick_labels'.
    try:
        bp = ax.boxplot(datos, tick_labels=etiq, patch_artist=True)
    except TypeError:
        bp = ax.boxplot(datos, labels=etiq, patch_artist=True)  # matplotlib < 3.9
    for caja in bp["boxes"]:
        caja.set(facecolor="#cfe0f1", edgecolor="#1f4e79")
    for med in bp["medians"]:
        med.set(color="#c00000", linewidth=1.5)
    ax.set_ylabel("Valor normalizado (0–1)")
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    plt.xticks(fontsize=8)
    plt.tight_layout()
    ruta = os.path.join(SALIDAS, "boxplots_5variables.png")
    plt.savefig(ruta, dpi=200); plt.close()
    log(f"Figura guardada: {ruta}")

    anom = {c: int(((df[c] < -1e-9) | (df[c] > 1+1e-9)).sum()) for c in cols}
    total_anom = sum(anom.values())
    if total_anom == 0:
        log("Control de outliers: ningún valor fuera del rango [0,1]. "
            "No se aplica filtrado (coherente con el apartado 4.7).")
    else:
        log(f"Control de outliers: {total_anom} valores fuera de [0,1] -> revisar: {anom}")


# ----------------------------------------------------------------------------
# 4. ENSEMBLE PU (100 Gradient Boosting) + SHAP promediado
# ----------------------------------------------------------------------------
def entrenar_pu(df, cols):
    from sklearn.ensemble import GradientBoostingClassifier
    rng = np.random.default_rng(SEMILLA)

    X = df[cols].values
    y = df["y"].values
    idx_pos = np.where(y == 1)[0]
    idx_unl = np.where(y == 0)[0]
    n_pos = len(idx_pos)
    n_muestra_unl = int(round(RATIO_UNL_POS * n_pos))

    scores_acum = np.zeros(len(df))
    modelos = []

    for i in range(N_MODELOS):
        sel_unl = rng.choice(idx_unl, size=min(n_muestra_unl, len(idx_unl)), replace=False)
        idx_train = np.concatenate([idx_pos, sel_unl])
        Xtr = X[idx_train]
        ytr = np.concatenate([np.ones(n_pos), np.zeros(len(sel_unl))])

        # [FIX 6] hiperparámetros explícitos, iguales a los del borrador.
        clf = GradientBoostingClassifier(random_state=SEMILLA + i, **GB_PARAMS)
        clf.fit(Xtr, ytr)
        modelos.append(clf)

        scores_acum += clf.predict_proba(X)[:, 1]

    df["pu_score"] = scores_acum / N_MODELOS
    log(f"Ensemble PU entrenado: {N_MODELOS} modelos Gradient Boosting "
        f"(proporción {RATIO_UNL_POS}:1 no etiquetadas:positivas, "
        f"max_depth={GB_PARAMS['max_depth']}, lr={GB_PARAMS['learning_rate']}).")
    return df, modelos, X


def shap_promedio(modelos, X, cols):
    """Importancia SHAP media sobre los 100 modelos del ensemble."""
    try:
        import shap
    except Exception:
        log("Aviso: 'shap' no instalado. Instálalo con  pip install shap")
        log("Se usa como respaldo la importancia interna de Gini promediada.")
        imp = np.mean([m.feature_importances_ for m in modelos], axis=0)
        return pd.Series(imp, index=cols), False

    aportes = np.zeros(len(cols))
    fallos = 0
    for m in modelos:
        try:
            sv = shap.TreeExplainer(m).shap_values(X)
            if isinstance(sv, list):
                sv = sv[-1]
            aportes += np.abs(sv).mean(axis=0)
        except Exception as e:
            fallos += 1
            if fallos == 1:
                log(f"  (SHAP falló en un modelo: {e}; se omiten los que fallen)")
    usados = len(modelos) - fallos
    if usados == 0:
        log("ERROR: SHAP falló en los 100 modelos; se usa la importancia de Gini.")
        imp = np.mean([m.feature_importances_ for m in modelos], axis=0)
        return pd.Series(imp, index=cols), False
    aportes /= usados
    log(f"SHAP promediado sobre {usados} de {len(modelos)} modelos del ensemble.")
    return pd.Series(aportes, index=cols), True


# ----------------------------------------------------------------------------
# 5. FIGURAS Y TABLAS DE RESULTADOS
# ----------------------------------------------------------------------------
def figura_distribucion(df):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    no_etq = df[df["y"] == 0]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(no_etq["pu_score"], bins=25, color="#4a90c2", edgecolor="white")
    ax.set_xlabel("Similitud con las estaciones con cargador rápido")
    ax.set_ylabel("Número de estaciones")
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    plt.tight_layout()
    ruta = os.path.join(SALIDAS, "distribucion_pu_score.png")
    plt.savefig(ruta, dpi=200); plt.close()
    log(f"Figura guardada: {ruta}")


def figura_shap(imp, es_shap):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    imp_pct = 100 * imp / imp.sum()
    orden = imp_pct.sort_values(ascending=True)
    fig, ax = plt.subplots(figsize=(9, 5))
    etiq = [ETIQUETAS[c] for c in orden.index]
    ax.barh(etiq, orden.values, color="#1f4e79")
    for yv, v in enumerate(orden.values):
        ax.text(v + 0.5, yv, f"{v:.1f} %", va="center", fontsize=9)
    xlabel = ("Importancia SHAP media (% del total)" if es_shap
              else "Importancia media del modelo (% del total)")
    ax.set_xlabel(xlabel)
    ax.set_xlim(0, max(orden.values) * 1.18)
    plt.tight_layout()
    ruta = os.path.join(SALIDAS, "shap_importancia_media.png")
    plt.savefig(ruta, dpi=200); plt.close()
    log(f"Figura guardada: {ruta}")
    return imp_pct


def tabla_ranking(df):
    no_etq = df[df["y"] == 0].copy()
    top = no_etq.sort_values("pu_score", ascending=False).head(10).reset_index(drop=True)
    top.insert(0, "Rango", top.index + 1)

    # [FIX 5] identificador compuesto + ubicación, en vez de solo 'Rotulo'.
    salida = top[["Rango", "Estacion_id", "Ubicacion",
                  "C1", "C2", "C3", "C4", "C5", "pu_score"]].copy()
    salida = salida.rename(columns={"Estacion_id": "Estación",
                                    "Ubicacion": "Dirección",
                                    "pu_score": "PU score"})
    for c in ["C1", "C2", "C3", "C4", "C5"]:
        salida[c] = salida[c].round(3)
    salida["PU score"] = salida["PU score"].round(3)
    ruta_csv = os.path.join(SALIDAS, "ranking_top10.csv")
    salida.to_csv(ruta_csv, index=False, encoding="utf-8-sig")
    log(f"Tabla guardada: {ruta_csv}")

    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    # la dirección se recorta y las columnas llevan ancho explícito para que
    # el texto largo no invada la columna contigua
    salida_img = salida.copy()
    salida_img["Dirección"] = salida_img["Dirección"].str.slice(0, 30)
    anchos = [0.05, 0.20, 0.27, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08]
    fig, ax = plt.subplots(figsize=(13, 3.3)); ax.axis("off")
    t = ax.table(cellText=salida_img.values, colLabels=salida_img.columns,
                 cellLoc="center", loc="center", colWidths=anchos)
    t.auto_set_font_size(False); t.set_fontsize(7.5); t.scale(1, 1.4)
    for j in range(len(salida_img.columns)):
        c = t[0, j]; c.set_facecolor("#1f4e79"); c.set_text_props(color="white", weight="bold")
    plt.tight_layout()
    ruta_png = os.path.join(SALIDAS, "ranking_top10.png")
    plt.savefig(ruta_png, dpi=200, bbox_inches="tight"); plt.close()
    log(f"Figura guardada: {ruta_png}")

    (no_etq[["Estacion_id", "Ubicacion", "pu_score"]]
        .sort_values("pu_score", ascending=False)
        .to_csv(os.path.join(SALIDAS, "scores_pu_todas.csv"),
                index=False, encoding="utf-8-sig"))


def tabla_comparacion(imp_pct):
    filas = []
    for c in ["C1", "C2", "C3", "C4", "C5"]:
        filas.append({
            "Variable": ETIQUETAS[c],
            "Peso AHP (%)": PESOS_AHP[c],
            "Importancia modelo (%)": round(float(imp_pct[c]), 1),
            "Diferencia (pp)": round(float(imp_pct[c]) - PESOS_AHP[c], 1),
        })
    comp = pd.DataFrame(filas)
    ruta = os.path.join(SALIDAS, "comparacion_shap_ahp.csv")
    comp.to_csv(ruta, index=False, encoding="utf-8-sig")
    log(f"Tabla guardada: {ruta}")
    log("\nContraste SHAP (modelo) vs AHP (experto):")
    for _, r in comp.iterrows():
        log(f"  {r['Variable']:<34} AHP {r['Peso AHP (%)']:>5} %  |  "
            f"modelo {r['Importancia modelo (%)']:>5} %  |  Δ {r['Diferencia (pp)']:+.1f} pp")


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
def main():
    log("="*74)
    log("BLOQUE III — Modelo PU + SHAP con las 5 variables (sin filtro IQR)")
    log("="*74)

    df, campos_x, normalizar_aqui, campo_pos, campos_id = cargar_datos()
    df, cols = preparar(df, campos_x, normalizar_aqui, campo_pos, campos_id)

    figura_boxplots(df, cols)                 # -> apartado 4.7
    df, modelos, X = entrenar_pu(df, cols)
    imp, es_shap = shap_promedio(modelos, X, cols)

    figura_distribucion(df)
    imp_pct = figura_shap(imp, es_shap)
    tabla_ranking(df)
    tabla_comparacion(imp_pct)

    with open(os.path.join(SALIDAS, "resumen_consola.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(LOG))
    log("\nListo. Revisa la carpeta: " + SALIDAS)

if __name__ == "__main__":
    main()
