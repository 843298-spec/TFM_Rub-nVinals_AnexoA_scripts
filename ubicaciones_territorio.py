# -*- coding: utf-8 -*-
"""
ubicaciones_territorio.py  (v2 — normalización idéntica al modelo EESS)
-----------------------------------------------------------------------
Aplica el modelo multicriterio Life Freesve SIN restringir los candidatos
a las gasolineras existentes: candidatos cada ESPACIADO m a lo largo de
la red viaria, puntuados con los MISMOS criterios, pesos AHP y esquema de
normalización que EESS_aragon_25830:

  - C2 (IMD) y C3 (población): log(1+x) antes de normalizar
  - C1, C4, C5: valor directo
  - Nulos: población -> 0; nubosidad -> mínimo de la serie
  - Campos de salida: C1_dist..C5_nub, C1_n..C5_n, IDONEIDAD (0-100)

Selección final: greedy por idoneidad descendente con separación mínima,
para evitar que el top se encadene en un único corredor de alta IMD.

Salidas: candidatos_territorio (todos) y ubicaciones_territorio_top.
Requiere Spatial Analyst (extracción de nubosidad).
"""

import arcpy
import math

# =====================================================================
# 1. CONFIGURACIÓN — AJUSTA ESTAS LÍNEAS
# =====================================================================
GDB             = r"E:\Clase\TFM\GasolinerasTFM\GasolinerasTFM.gdb"
CAPA_RED        = "red_viaria_aragon"        # 2.503 tramos unificados
CAMPO_IMD       = "IMD_FINAL"                # verifica el nombre exacto
CAPA_CARGADORES = "cargadores_AFIR_25830"    # 38 cargadores >=150 kW
CAPA_NUCLEOS    = "t112_nucleos"             # núcleos de población (polígonos)
CAMPO_POB       = "poblacion"                # habitantes por núcleo
RASTER_NUBES    = r"E:\Clase\TFM\nubosidad_aragon_pct.tif"

ESPACIADO       = 2000               # m entre candidatos sobre la red
RADIO_POB       = "10 Kilometers"    # radio del criterio C3
TOP_N           = 50                 # nº de ubicaciones finales
MIN_SEPARACION  = 20000              # m mínimos entre seleccionadas

# Pesos AHP (idénticos al modelo EESS)
W = {"C2": 0.417, "C1": 0.263, "C4": 0.160, "C3": 0.097, "C5": 0.062}
# =====================================================================

arcpy.env.workspace = GDB
arcpy.env.overwriteOutput = True
arcpy.CheckOutExtension("Spatial")
from arcpy.sa import ExtractMultiValuesToPoints

def resolver(nombre):
    """Acepta: nombre de capa del mapa activo, ruta completa, o nombre en la GDB."""
    if arcpy.Exists(nombre):
        return nombre
    ruta = f"{GDB}\\{nombre}"
    if arcpy.Exists(ruta):
        return ruta
    raise SystemExit(f"[ERROR] No encuentro '{nombre}' ni en el mapa ni en la GDB. "
                     f"Revisa el nombre o usa la ruta completa.")

red        = resolver(CAPA_RED)
cargadores = resolver(CAPA_CARGADORES)
nucleos    = resolver(CAPA_NUCLEOS)
if not arcpy.Exists(RASTER_NUBES):
    raise SystemExit(f"[ERROR] No encuentro el ráster: {RASTER_NUBES}")

# ---------------------------------------------------------------
# PASO 1: candidatos a lo largo de la red (solo tramos con IMD)
# ---------------------------------------------------------------
print("1/6 Generando candidatos sobre la red...")
red_lyr = arcpy.management.MakeFeatureLayer(
    red, "red_lyr", f"{CAMPO_IMD} IS NOT NULL AND {CAMPO_IMD} > 0"
).getOutput(0)

pts_brutos = f"{GDB}\\cand_brutos"
arcpy.management.GeneratePointsAlongLines(
    red_lyr, pts_brutos, "DISTANCE",
    Distance=f"{ESPACIADO} meters", Include_End_Points="NO_END_POINTS"
)
n0 = int(arcpy.management.GetCount(pts_brutos)[0])
print(f"   {n0} candidatos generados (heredan {CAMPO_IMD} de su tramo)")

# ---------------------------------------------------------------
# PASO 2: C3 población en 10 km (Spatial Join con suma)
# ---------------------------------------------------------------
print("2/6 Calculando población en 10 km (C3)...")
fm = arcpy.FieldMappings()
fm.addTable(pts_brutos)
fmap = arcpy.FieldMap()
fmap.addInputField(nucleos, CAMPO_POB)
fmap.mergeRule = "Sum"
salida = fmap.outputField
salida.name, salida.aliasName = "C3_pob", "C3_pob"
fmap.outputField = salida
fm.addFieldMap(fmap)

candidatos = f"{GDB}\\candidatos_territorio"
arcpy.analysis.SpatialJoin(
    pts_brutos, nucleos, candidatos, "JOIN_ONE_TO_ONE", "KEEP_ALL",
    fm, "WITHIN_A_DISTANCE", RADIO_POB
)

# ---------------------------------------------------------------
# PASO 3: C1, C2 y C4 (Near sobreescribe NEAR_DIST -> campo propio)
# ---------------------------------------------------------------
print("3/6 Distancias a cargadores (C1) y a núcleos (C4)...")
arcpy.analysis.Near(candidatos, cargadores, method="PLANAR")
arcpy.management.CalculateField(candidatos, "C1_dist", "!NEAR_DIST!",
                                "PYTHON3", field_type="DOUBLE")

arcpy.analysis.Near(candidatos, nucleos, method="PLANAR")
arcpy.management.CalculateField(candidatos, "C4_dist", "!NEAR_DIST!",
                                "PYTHON3", field_type="DOUBLE")

# C2: copia de la IMD heredada a un campo con el nombre estándar
arcpy.management.CalculateField(candidatos, "C2_imd", f"!{CAMPO_IMD}!",
                                "PYTHON3", field_type="DOUBLE")

# ---------------------------------------------------------------
# PASO 4: C5 nubosidad desde el ráster MODIS
# ---------------------------------------------------------------
print("4/6 Extrayendo nubosidad (C5)...")
ExtractMultiValuesToPoints(candidatos, [[RASTER_NUBES, "C5_nub"]])

# ---------------------------------------------------------------
# PASO 5: normalización e IDONEIDAD (esquema idéntico al modelo EESS)
# ---------------------------------------------------------------
print("5/6 Normalizando criterios y calculando IDONEIDAD...")
campos = ["C1_dist", "C2_imd", "C3_pob", "C4_dist", "C5_nub"]
datos = []
with arcpy.da.SearchCursor(candidatos, campos) as cur:
    for row in cur:
        datos.append(list(row))

def col(i):
    return [d[i] if d[i] is not None else 0 for d in datos]

c1 = col(0); c2 = col(1); c3 = col(2); c4 = col(3)
c5 = [d[4] for d in datos if d[4] is not None]   # nulos fuera del rango
c2log = [math.log(1 + max(0, v)) for v in c2]
c3log = [math.log(1 + max(0, v)) for v in c3]

c1min, c1max = min(c1), max(c1)
c2min, c2max = min(c2log), max(c2log)
c3min, c3max = min(c3log), max(c3log)
c4min, c4max = min(c4), max(c4)
c5min, c5max = min(c5), max(c5)

def norm(v, vmin, vmax, invertir=False):
    if vmax == vmin:
        return 0.5
    x = (v - vmin) / (vmax - vmin)
    return 1 - x if invertir else x

nuevos = ["C1_n", "C2_n", "C3_n", "C4_n", "C5_n", "IDONEIDAD"]
existentes = [f.name for f in arcpy.ListFields(candidatos)]
for nombre in nuevos:
    if nombre not in existentes:
        arcpy.management.AddField(candidatos, nombre, "DOUBLE")

campos_w = campos + nuevos
with arcpy.da.UpdateCursor(candidatos, campos_w) as cur:
    for row in cur:
        v_c1 = row[0] or 0
        v_c2 = math.log(1 + max(0, row[1] or 0))
        v_c3 = math.log(1 + max(0, row[2] or 0))
        v_c4 = row[3] or 0
        v_c5 = row[4] if row[4] is not None else c5min
        n1 = norm(v_c1, c1min, c1max)                  # más lejos mejor
        n2 = norm(v_c2, c2min, c2max)                  # más IMD mejor
        n3 = norm(v_c3, c3min, c3max)                  # más población mejor
        n4 = norm(v_c4, c4min, c4max, invertir=True)   # más cerca mejor
        n5 = norm(v_c5, c5min, c5max, invertir=True)   # menos nubes mejor
        idon = (W["C1"] * n1 + W["C2"] * n2 + W["C3"] * n3 +
                W["C4"] * n4 + W["C5"] * n5) * 100
        row[5], row[6], row[7], row[8], row[9] = n1, n2, n3, n4, n5
        row[10] = round(idon, 2)
        cur.updateRow(row)

# ---------------------------------------------------------------
# PASO 6: selección greedy con separación mínima
# ---------------------------------------------------------------
print("6/6 Seleccionando TOP con separación mínima...")
with arcpy.da.SearchCursor(candidatos, ["OID@", "SHAPE@X", "SHAPE@Y", "IDONEIDAD"]) as cur:
    puntos = sorted(cur, key=lambda r: r[3], reverse=True)

sel = []
for oid, x, y, idon in puntos:
    if len(sel) >= TOP_N:
        break
    if all((x - sx) ** 2 + (y - sy) ** 2 >= MIN_SEPARACION ** 2
           for _, sx, sy, _ in sel):
        sel.append((oid, x, y, idon))

oid_field = arcpy.Describe(candidatos).OIDFieldName
oids = ",".join(str(s[0]) for s in sel)
lyr = arcpy.management.MakeFeatureLayer(
    candidatos, "sel_lyr", f"{oid_field} IN ({oids})"
).getOutput(0)
arcpy.management.CopyFeatures(lyr, f"{GDB}\\ubicaciones_territorio_top")
arcpy.management.Delete(pts_brutos)

# ---------------------------------------------------------------
# RESUMEN (mismas estadísticas que el modelo EESS, para comparar)
# ---------------------------------------------------------------
vals = sorted(p[3] for p in puntos)
n = len(vals)
print("\n================ RESUMEN ================")
print(f"ÍNDICE DE IDONEIDAD (0-100) sobre {n} candidatos territoriales:")
print(f"  min: {vals[0]:.1f}")
print(f"  P25: {vals[int(n*0.25)]:.1f}")
print(f"  mediana: {vals[int(n*0.50)]:.1f}")
print(f"  P75: {vals[int(n*0.75)]:.1f}")
print(f"  P90: {vals[int(n*0.90)]:.1f}")
print(f"  max: {vals[-1]:.1f}")
print(f"\nSeleccionadas: {len(sel)} (separación mínima {MIN_SEPARACION/1000:.0f} km)")
print("Top 10:")
for k, (oid, x, y, idon) in enumerate(sel[:10], 1):
    print(f"  {k:>2}. IDONEIDAD {idon:6.2f}   ({x:,.0f}, {y:,.0f})")
print("\nCapas creadas: candidatos_territorio, ubicaciones_territorio_top")
print("Hecho.")
