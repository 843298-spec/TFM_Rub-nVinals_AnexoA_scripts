"""
tfm_05_figuras_contraste.py

Genera las dos figuras de contraste entre el modelo PU (aprendizaje automático)
y el AHP (ponderación de experto), que no produce modelo_pu_bloque3.py:

  - comparacion_shap_ahp.png   : barras agrupadas, peso AHP vs importancia SHAP
  - dispersion_pu_vs_ahp.png   : PU score frente a IDONEIDAD por provincia

Ambas en español y sin título interno, para insertarlas directamente en la
memoria. Requiere haber ejecutado antes modelo_pu_bloque3.py.
"""

from __future__ import annotations

import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

GDB = r"E:\Clase\TFM\GasolinerasTFM\GasolinerasTFM.gdb"
CAPA = "EESS_aragon_25830_PU"
SALIDAS = Path(r"E:\Clase\TFM\Git\salidas_bloque3")

AZUL = "#1f4e79"
NARANJA = "#c55a11"
COLOR_PROV = {"ZARAGOZA": "#1f4e79", "HUESCA": "#4a90c2", "TERUEL": "#c55a11"}


def figura_comparacion(comp: pd.DataFrame) -> None:
    etiquetas = [v.replace(" · ", "\n") for v in comp["Variable"]]
    x = np.arange(len(comp))
    ancho = 0.38

    fig, ax = plt.subplots(figsize=(10, 5.2))
    b1 = ax.bar(x - ancho / 2, comp["Peso AHP (%)"], ancho,
                label="Peso AHP (experto)", color=AZUL)
    b2 = ax.bar(x + ancho / 2, comp["Importancia modelo (%)"], ancho,
                label="Importancia SHAP (modelo PU)", color=NARANJA)

    for barras in (b1, b2):
        for b in barras:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.6,
                    f"{b.get_height():.1f}", ha="center", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(etiquetas, fontsize=8)
    ax.set_ylabel("Peso / importancia (% del total)")
    ax.set_ylim(0, max(comp[["Peso AHP (%)", "Importancia modelo (%)"]].max()) * 1.20)
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    ax.legend(frameon=False, fontsize=9)
    plt.tight_layout()
    ruta = SALIDAS / "comparacion_shap_ahp.png"
    plt.savefig(ruta, dpi=200)
    plt.close()
    print(f"Figura guardada: {ruta}")


def figura_dispersion(m: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.5))

    for prov, color in COLOR_PROV.items():
        sub = m[m["Provincia"].str.upper() == prov]
        ax.scatter(sub["pu_score"], sub["IDONEIDAD"], s=18, alpha=0.65,
                   color=color, label=prov.capitalize(), edgecolors="none")

    rho = m["pu_score"].corr(m["IDONEIDAD"], method="spearman")
    ax.set_xlabel("PU score (similitud con estaciones que ya tienen cargador)")
    ax.set_ylabel("IDONEIDAD (score AHP)")
    ax.grid(linestyle=":", alpha=0.5)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    ax.text(0.02, 0.97, f"Correlación de Spearman: ρ = {rho:.3f}",
            transform=ax.transAxes, va="top", fontsize=9,
            bbox=dict(boxstyle="round,pad=0.35", facecolor="white",
                      edgecolor="#999999", alpha=0.9))
    plt.tight_layout()
    ruta = SALIDAS / "dispersion_pu_vs_ahp.png"
    plt.savefig(ruta, dpi=200)
    plt.close()
    print(f"Figura guardada: {ruta}")


def main() -> None:
    comp = pd.read_csv(SALIDAS / "comparacion_shap_ahp.csv", encoding="utf-8-sig")
    figura_comparacion(comp)

    eess = gpd.read_file(GDB, layer=CAPA).reset_index(drop=True)
    eess["OBJECTID"] = range(1, len(eess) + 1)
    eess["Estacion_id"] = (
        eess["OBJECTID"].astype(str).str.zfill(3) + " · "
        + eess["Rotulo"].fillna("").str.strip()
    )
    scores = pd.read_csv(SALIDAS / "scores_pu_todas.csv", encoding="utf-8-sig")
    m = eess.merge(scores[["Estacion_id", "pu_score"]], on="Estacion_id", how="inner")
    print(f"Estaciones no etiquetadas cruzadas: {len(m)}")
    figura_dispersion(m)


if __name__ == "__main__":
    main()
