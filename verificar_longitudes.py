# -*- coding: utf-8 -*-
"""
verificar_longitudes.py
-----------------------
Chequeo de sanidad de las longitudes de la red, para confirmar que las
cifras de km son coherentes con la estadística oficial de Aragón.

Referencia oficial (ICEARAGON / MITMA):
  - Carreteras nacionales en Aragón: ~1.966 km
  - Red básica autonómica: ~1.872 km
  - Red comarcal autonómica: ~2.491 km
  => La red principal (la que se analiza) ronda los 5.000-6.500 km.

Si la longitud total de la capa completa (2.503 tramos) cae en ese orden,
el pipeline es consistente. Los 3.757 km en déficit son un subconjunto.
"""

import arcpy

GDB = r"E:\Clase\TFM\GasolinerasTFM\GasolinerasTFM.gdb"

# Ajusta si el nombre difiere:
CAPA_COMPLETA = "NOMBRE_CAPA_RED_COMPLETA"  # los 2.503 tramos (nacional+DGA)
CAPA_DEFICIT  = "Déficit AFIR"              # los 1.988 en déficit


def estadisticas(capa, etiqueta):
    n = 0
    total_m = 0.0
    minimo = float("inf")
    maximo = 0.0
    with arcpy.da.SearchCursor(capa, ["SHAPE@LENGTH"]) as cur:
        for (longitud,) in cur:
            L = longitud or 0
            n += 1
            total_m += L
            minimo = min(minimo, L)
            maximo = max(maximo, L)
    if n == 0:
        print(f"{etiqueta}: sin registros")
        return
    print(f"\n=== {etiqueta} ===")
    print(f"  Tramos:            {n}")
    print(f"  Longitud total:    {total_m/1000:,.1f} km")
    print(f"  Media por tramo:   {total_m/n/1000:,.2f} km")
    print(f"  Tramo más corto:   {minimo/1000:,.3f} km")
    print(f"  Tramo más largo:   {maximo/1000:,.2f} km")


estadisticas(f"{GDB}\\{CAPA_COMPLETA}", "RED COMPLETA (2.503 tramos)")
estadisticas(f"{GDB}\\{CAPA_DEFICIT}",  "RED EN DÉFICIT (1.988 tramos)")

print("\nInterpretación:")
print("  - Si la red completa da ~5.000-6.500 km -> coherente con datos oficiales.")
print("  - Media por tramo ~2 km es normal para una red de rango nacional/autonómico.")
print("  - Los 3.757 km en déficit deben ser < longitud total de la red completa.")
