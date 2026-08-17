# -*- coding: utf-8 -*-
"""
severidad_por_provincia_sjoin.py
--------------------------------
Asigna cada tramo de "Déficit AFIR" a su provincia mediante Spatial Join
y calcula tramos y km por SEVERIDAD (Crítico/Alto/Medio/Bajo) y provincia.

Los tramos que cruzan un límite provincial se asignan a UNA sola provincia
según dónde caiga su centroide (match_option HAVE_THEIR_CENTER_IN), que es
lo estándar para este tipo de conteo.

Control (total Aragón): Crítico 382 · Alto 5 · Medio 859 · Bajo 742 = 1.988
Km: 1110,62 / 9,31 / 2022,44 / 614,46 = 3756,83
"""

import arcpy
from collections import defaultdict

# =====================================================================
# AJUSTA ESTAS LÍNEAS
# =====================================================================
GDB        = r"E:\Clase\TFM\GasolinerasTFM\GasolinerasTFM.gdb"
CAPA       = "Déficit AFIR"
CAPA_PROV  = "Prov_Aragon_25830"        # capa de las 3 provincias
CAMPO_PROV = "Nombre"                    # campo con Huesca / Teruel / Zaragoza
CAMPO_SEV  = "SEVERIDAD"
CAMPO_LONG = "NOMBRE_CAMPO_LONGITUD"    # <-- AJUSTA: tu campo de longitud en metros
                                         #     (o pon "SHAPE@LENGTH" para recalcular al vuelo)
GUARDAR    = True
# =====================================================================

capa = f"{GDB}\\{CAPA}"
prov = f"{GDB}\\{CAPA_PROV}"

# --- Spatial Join: cada tramo hereda la provincia de su centroide ---
SJOIN = f"{GDB}\\deficit_con_provincia"
if arcpy.Exists(SJOIN):
    arcpy.management.Delete(SJOIN)
arcpy.analysis.SpatialJoin(
    target_features=capa,
    join_features=prov,
    out_feature_class=SJOIN,
    join_operation="JOIN_ONE_TO_ONE",
    join_type="KEEP_ALL",
    match_option="HAVE_THEIR_CENTER_IN"
)
print(f"[OK] Spatial Join creado: deficit_con_provincia")

# --- Acumular km y tramos por (provincia, severidad) ---
acum = defaultdict(lambda: [0.0, 0])
provincias = set()
with arcpy.da.SearchCursor(SJOIN, [CAMPO_PROV, CAMPO_SEV, CAMPO_LONG]) as cur:
    for p, s, longitud in cur:
        p = p if p not in (None, "") else "(sin provincia)"
        s = s if s not in (None, "") else "(sin dato)"
        acum[(p, s)][0] += (longitud or 0) / 1000.0
        acum[(p, s)][1] += 1
        provincias.add(p)

niveles = ["Crítico", "Critico", "Alto", "Medio", "Bajo"]
sev_presentes = sorted({s for (_, s) in acum},
                       key=lambda s: (niveles.index(s) if s in niveles else 99, str(s)))

def imprime(idx, titulo, fmt):
    print(f"\n=== {titulo} ===")
    cab = f"{'Provincia':<14}" + "".join(f"{s:>10}" for s in sev_presentes) + f"{'TOTAL':>10}"
    print(cab); print("-" * len(cab))
    for p in sorted(provincias):
        fila = f"{str(p):<14}"; tot = 0
        for s in sev_presentes:
            v = acum[(p, s)][idx]; tot += v
            fila += fmt.format(v)
        fila += fmt.format(tot)
        print(fila)

imprime(1, "Nº DE TRAMOS POR PROVINCIA Y SEVERIDAD", "{:>10.0f}")
imprime(0, "KM POR PROVINCIA Y SEVERIDAD", "{:>10.1f}")

# --- Guardar tabla larga ---
if GUARDAR:
    ruta = f"{GDB}\\severidad_por_provincia"
    if arcpy.Exists(ruta):
        arcpy.management.Delete(ruta)
    arcpy.management.CreateTable(GDB, "severidad_por_provincia")
    arcpy.management.AddField(ruta, "Provincia", "TEXT", field_length=50)
    arcpy.management.AddField(ruta, "Severidad", "TEXT", field_length=50)
    arcpy.management.AddField(ruta, "Km", "DOUBLE")
    arcpy.management.AddField(ruta, "N_Tramos", "LONG")
    with arcpy.da.InsertCursor(ruta, ["Provincia", "Severidad", "Km", "N_Tramos"]) as ic:
        for (p, s), (km, n) in acum.items():
            ic.insertRow([str(p), str(s), round(km, 2), n])
    print("\n[OK] Tabla guardada: severidad_por_provincia")

print("\nHecho.")
