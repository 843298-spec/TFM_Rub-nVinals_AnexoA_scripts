# -*- coding: utf-8 -*-
"""
km_severidad.py
---------------
Calcula los KILÓMETROS de red por nivel de SEVERIDAD sobre la capa
"Déficit AFIR" (1.988 tramos en déficit), tal como pidió Cristian:
con muchos tramos cortos, el conteo de tramos puede sobredimensionar
el problema frente a los km realmente afectados.

Usa el campo de longitud en metros ya existente en la capa.
Cifras de control: Crítico 382 / Alto 5 / Medio 859 / Bajo 742 = 1.988.
"""

import arcpy
from collections import defaultdict

# =====================================================================
# AJUSTA ESTAS LÍNEAS
# =====================================================================
GDB        = r"E:\Clase\TFM\GasolinerasTFM\GasolinerasTFM.gdb"
CAPA       = "Déficit AFIR"          # capa de 1.988 tramos en déficit
CAMPO_SEV  = "SEVERIDAD"             # Crítico / Alto / Medio / Bajo
CAMPO_LONG = "NOMBRE_CAMPO_LONGITUD" # <-- tu campo de longitud en metros
GUARDAR    = True                    # escribe tabla km_por_severidad en la GDB
# =====================================================================

capa = f"{GDB}\\{CAPA}"

km = defaultdict(float)
n  = defaultdict(int)
with arcpy.da.SearchCursor(capa, [CAMPO_SEV, CAMPO_LONG]) as cur:
    for sev, longitud in cur:
        clave = sev if sev not in (None, "") else "(sin dato)"
        km[clave] += (longitud or 0) / 1000.0   # metros -> km
        n[clave]  += 1

total_km = sum(km.values())
total_n  = sum(n.values())

orden = ["Crítico", "Critico", "Alto", "Medio", "Bajo"]
claves = sorted(km, key=lambda k: (orden.index(k) if k in orden else 99, str(k)))

print("=== KM DE RED EN DÉFICIT POR SEVERIDAD ===")
print(f"{'Severidad':<14}{'Tramos':>9}{'Km':>13}{'% Km':>9}")
print("-" * 45)
for k in claves:
    pct = km[k] / total_km * 100 if total_km else 0
    print(f"{str(k):<14}{n[k]:>9}{km[k]:>13.2f}{pct:>8.1f}%")
print("-" * 45)
print(f"{'TOTAL':<14}{total_n:>9}{total_km:>13.2f}{100.0:>8.1f}%")

# --- Guardar tabla para la infografía ---
if GUARDAR:
    ruta = f"{GDB}\\km_por_severidad"
    if arcpy.Exists(ruta):
        arcpy.management.Delete(ruta)
    arcpy.management.CreateTable(GDB, "km_por_severidad")
    arcpy.management.AddField(ruta, "Severidad", "TEXT", field_length=50)
    arcpy.management.AddField(ruta, "Km", "DOUBLE")
    arcpy.management.AddField(ruta, "N_Tramos", "LONG")
    with arcpy.da.InsertCursor(ruta, ["Severidad", "Km", "N_Tramos"]) as ic:
        for k in claves:
            ic.insertRow([str(k), round(km[k], 2), n[k]])
    print("\n[OK] Tabla guardada: km_por_severidad")

print("\nHecho.")
