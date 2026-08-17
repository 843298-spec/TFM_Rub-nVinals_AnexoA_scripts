"""
tfm_04_etiqueta_y_c1_corregido.py

Prepara la capa de entrada del modelo PU del Bloque III a partir de la GDB del
proyecto, resolviendo dos problemas de la capa EESS_aragon_25830:

  1. No tiene etiqueta positiva. El modelo PU la necesita y no puede inventarla.
     Se calcula igual que en tfm_03: positiva = gasolinera co-ubicada
     (<= UMBRAL_COLOCACION_M) con un punto de recarga de potencia >= UMBRAL_KW_RAPIDA.

  2. C1 ("distancia a recarga rápida") tiene fuga de etiqueta: está medida contra
     el cargador más cercano SIN excluir el que está en la propia gasolinera, por
     lo que para las positivas vale ~0 por construcción (media 41,7 m frente a
     6.124 m en las no etiquetadas). Entrenar con ese C1 hace que el modelo
     "aprenda" la propia definición de la etiqueta y que su importancia SHAP sea
     circular. Se recalcula C1 excluyendo el cargador co-ubicado (para las
     positivas se usa el segundo más cercano) y contando solo recarga rápida.

Salida: nueva feature class EESS_aragon_25830_PU dentro de la misma GDB, con
todos los campos originales más:

    Has_fast_charger : 0/1, etiqueta PU
    C1_corr_dist     : distancia (m) a la recarga rápida más cercana que no es la propia
    C1_corr_n        : C1_corr_dist normalizada 0-1 (min-max directo, igual que C1_n)

La capa original NO se modifica. Hay copia de seguridad de la GDB en
E:\\Clase\\TFM\\Git\\backups\\.

Ejecutar con el entorno conda del proyecto (geopandas + scipy); no requiere arcpy.
"""

from __future__ import annotations

import logging
import re

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

GDB = r"E:\Clase\TFM\GasolinerasTFM\GasolinerasTFM.gdb"
CAPA_EESS = "EESS_aragon_25830"
CAPA_PR = "PR_Aragon_25830"
CAPA_SALIDA = "EESS_aragon_25830_PU"

UMBRAL_KW_RAPIDA = 50.0      # kW mínimos para considerar el conector "rápido" (DC)
UMBRAL_COLOCACION_M = 100.0  # distancia máxima para considerar el PR "en la propia gasolinera"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("tfm04")

KW_PATTERN = re.compile(r"\(([\d.,]+)\s*kw\)", re.IGNORECASE)


def potencia_maxima_kw(texto_conectores: str) -> float:
    """Potencia máxima (kW) declarada en el campo 'Conectores'."""
    if not isinstance(texto_conectores, str) or not texto_conectores.strip():
        return 0.0
    valores = [
        float(match.replace(",", "."))
        for match in KW_PATTERN.findall(texto_conectores)
    ]
    return max(valores) if valores else 0.0


def cargar_recarga_rapida() -> gpd.GeoDataFrame:
    pr = gpd.read_file(GDB, layer=CAPA_PR)

    # La capa trae POT_KW ya calculado; si falta, se parsea de "Conectores".
    if "POT_KW" in pr.columns and pr["POT_KW"].notna().any():
        pr["potencia_max_kw"] = pd.to_numeric(pr["POT_KW"], errors="coerce").fillna(0.0)
        origen = "campo POT_KW"
    else:
        pr["potencia_max_kw"] = pr["Conectores"].apply(potencia_maxima_kw)
        origen = "parseo de Conectores"

    rapidos = pr.loc[pr["potencia_max_kw"] >= UMBRAL_KW_RAPIDA].reset_index(drop=True)
    log.info(
        "Puntos de recarga: %d totales, %d rápidos (>=%.0f kW, potencia de %s)",
        len(pr), len(rapidos), UMBRAL_KW_RAPIDA, origen,
    )
    if rapidos.empty:
        raise ValueError("Ningún punto de recarga supera el umbral de potencia rápida.")
    return rapidos


def calcular_etiqueta_y_c1(
    eess: gpd.GeoDataFrame,
    recarga_rapida: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Etiqueta PU y distancia a la competencia rápida sin fuga de etiqueta."""
    coords_eess = np.column_stack([eess.geometry.x, eess.geometry.y])
    coords_pr = np.column_stack([recarga_rapida.geometry.x, recarga_rapida.geometry.y])

    k = min(2, len(coords_pr))
    distancias, _ = cKDTree(coords_pr).query(coords_eess, k=k)
    if k == 1:
        distancias = distancias.reshape(-1, 1)

    dist_1 = distancias[:, 0]
    dist_2 = distancias[:, 1] if k > 1 else np.full_like(dist_1, np.nan)

    es_positiva = dist_1 <= UMBRAL_COLOCACION_M

    # Para las positivas el primer cargador es "el suyo": se usa el segundo.
    c1_corr = np.where(es_positiva, dist_2, dist_1)
    centinela = np.nanmax(distancias) * 2 if np.isfinite(np.nanmax(distancias)) else 0.0
    c1_corr = np.where(np.isnan(c1_corr), centinela, c1_corr)

    salida = eess.copy()
    salida["Has_fast_charger"] = es_positiva.astype(int)
    salida["C1_corr_dist"] = np.round(c1_corr, 2)

    # Misma normalización que C1_n en la capa original: min-max directo
    # (más lejos de un cargador rápido = mayor valor = más oportunidad).
    lo, hi = c1_corr.min(), c1_corr.max()
    salida["C1_corr_n"] = 0.0 if hi == lo else (c1_corr - lo) / (hi - lo)

    n_pos = int(es_positiva.sum())
    log.info(
        "Etiqueta: %d positivas de %d (%.1f %%), umbral colocación %.0f m",
        n_pos, len(salida), 100 * n_pos / len(salida), UMBRAL_COLOCACION_M,
    )
    log.info(
        "C1 original  -> positivas: media %.1f m | no etiquetadas: media %.1f m",
        eess.loc[es_positiva, "C1_dist"].mean(),
        eess.loc[~es_positiva, "C1_dist"].mean(),
    )
    log.info(
        "C1 corregido -> positivas: media %.1f m | no etiquetadas: media %.1f m",
        salida.loc[es_positiva, "C1_corr_dist"].mean(),
        salida.loc[~es_positiva, "C1_corr_dist"].mean(),
    )
    return salida


def main() -> None:
    eess = gpd.read_file(GDB, layer=CAPA_EESS)
    log.info("Capa %s: %d estaciones", CAPA_EESS, len(eess))

    recarga_rapida = cargar_recarga_rapida()
    salida = calcular_etiqueta_y_c1(eess, recarga_rapida)

    salida.to_file(GDB, layer=CAPA_SALIDA, driver="OpenFileGDB")
    log.info("Escrita capa %s en la GDB (%d filas, %d campos)",
             CAPA_SALIDA, len(salida), len(salida.columns))


if __name__ == "__main__":
    main()
