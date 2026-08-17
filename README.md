# Localización óptima de puntos de recarga ultrarrápida en Aragón (modelo Life Freesvee)

Scripts del Trabajo Fin de Máster de **Rubén Viñals**, del Máster Universitario
en Ciencia y Tecnología de la Información Geográfica (MTIG), Universidad de
Zaragoza. Curso 2025–2026. Director: Cristian Iranzo.

Este repositorio constituye el **Anexo A** de la memoria: reúne el código
empleado en el análisis. El trabajo desarrolla una metodología basada en
Sistemas de Información Geográfica (SIG) para diagnosticar el déficit de recarga
rápida de vehículo eléctrico en Aragón —según el criterio de cobertura del
Reglamento europeo AFIR (UE 2023/1804)— y localizar las ubicaciones óptimas
para el despliegue de las estaciones autónomas del proyecto Life Freesvee.

## Entorno

Los scripts pertenecen a dos entornos distintos:

- **ArcGIS Pro** con las extensiones *Network Analyst* y *Spatial Analyst*, y su
  **Python (arcpy)**, para el diagnóstico AFIR y el modelo territorial.
- **Python con `geopandas`, `scipy`, `scikit-learn` y `matplotlib`** (entorno
  conda, sin arcpy) para el modelo de validación por aprendizaje automático.
- **Google Earth Engine** para la capa de nubosidad (MODIS MOD09GA).
- Sistema de referencia común: **ETRS89 / UTM huso 30N (EPSG:25830)**.

## Contenido

| Script | Bloque | Función |
|---|---|---|
| `km_severidad.py` | Diagnóstico AFIR | Kilómetros de red en déficit por nivel de severidad |
| `severidad_por_provincia_sjoin.py` | Diagnóstico AFIR | Tramos y km por provincia y severidad (unión espacial por centroide) |
| `ubicaciones_territorio.py` | Localización | Modelo territorial: candidatos cada 2 km sobre la red, mismos criterios y pesos AHP, con selección por separación mínima |
| `verificar_longitudes.py` | Control de calidad | Longitudes totales, medias y extremas de las capas de red |
| `tfm_04_etiqueta_y_c1_corregido.py` | Validación (PU) | Prepara la capa de entrada del modelo PU: etiqueta las estaciones con recarga rápida co-ubicada y recalcula la distancia a recarga rápida corrigiendo la fuga de etiqueta |
| `modelo_pu_bloque3.py` | Validación (PU) | Modelo *Positive-Unlabeled* con *ensemble* de Gradient Boosting e interpretabilidad SHAP; genera los *scores* de similitud y el ranking de estaciones candidatas |
| `tfm_05_figuras_contraste.py` | Validación (PU) | Figuras de contraste entre el modelo PU y el AHP: importancia SHAP frente a peso del experto y dispersión de ambos scores por provincia |

> Cada script documenta en su cabecera sus entradas, salidas y parámetros
> ajustables. Los scripts de descarga de la capacidad eléctrica de la CNMC, de
> cálculo de los cinco criterios e índice AHP y del análisis de cobertura
> (Service Area) se incorporarán próximamente para completar el anexo.

## Datos

Este repositorio contiene **solo código**. Las capas de partida proceden de
fuentes públicas (MITMA, IDEAragón, INE, CNMC, geoportal de gasolineras y
NASA MODIS vía Google Earth Engine); su origen y año de referencia se detallan
en el capítulo de datos de la memoria. Las rutas locales que aparecen en los
scripts (`E:\Clase\TFM\...`) deben adaptarse al equipo donde se ejecuten.

## Cita

Viñals, R. (2026). *Localización óptima de puntos de recarga ultrarrápida para
vehículo eléctrico en Aragón: modelo Life Freesvee* [Código]. GitHub.
https://github.com/843298-spec/TFM_Rub-nVinals_AnexoA_scripts

## Licencia

Publicado bajo licencia MIT (véase el archivo `LICENSE`).
