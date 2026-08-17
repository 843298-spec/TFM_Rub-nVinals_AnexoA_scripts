# Localización óptima de puntos de recarga ultrarrápida en Aragón (modelo Life Freesve)

Código y scripts del Trabajo Fin de Máster de **Rubén Viñals**, del Máster
Universitario en Ciencia y Tecnología de la Información Geográfica (MTIG),
Universidad de Zaragoza. Curso 2025–2026. Director: Cristian Iranzo.

El trabajo desarrolla una metodología basada en Sistemas de Información
Geográfica (SIG) para diagnosticar el déficit de recarga rápida de vehículo
eléctrico en Aragón —según el criterio de cobertura del Reglamento europeo
AFIR (UE 2023/1804)— y localizar las ubicaciones óptimas para el despliegue
de las estaciones autónomas del proyecto Life Freesve.

## Entorno

- **ArcGIS Pro** con las extensiones *Network Analyst* y *Spatial Analyst*.
- **Python (arcpy)**, el intérprete que acompaña a ArcGIS Pro.
- **Google Earth Engine** para la capa de nubosidad (MODIS MOD09GA).
- Sistema de referencia común: **ETRS89 / UTM huso 30N (EPSG:25830)**.

## Contenido

Los scripts están en la carpeta [`scripts/`](scripts/):

| Script | Bloque | Función |
|---|---|---|
| `km_severidad.py` | Diagnóstico AFIR | Kilómetros de red en déficit por nivel de severidad |
| `severidad_por_provincia_sjoin.py` | Diagnóstico AFIR | Tramos y km por provincia y severidad (unión espacial por centroide) |
| `ubicaciones_territorio.py` | Localización | Modelo territorial: candidatos cada 2 km sobre la red, mismos criterios y pesos AHP, selección con separación mínima |
| `verificar_longitudes.py` | Control de calidad | Longitudes totales, medias y extremas de las capas de red |

> Nota: los scripts de descarga de la capacidad eléctrica de la CNMC, de
> cálculo de los criterios y del índice AHP, y del análisis de cobertura
> (Service Area) se incorporarán a este repositorio. Cada script incluye en
> su cabecera la descripción de sus entradas, salidas y parámetros ajustables.

## Datos

Este repositorio contiene **solo código**. Las capas de partida proceden de
fuentes públicas (MITMA, IDEAragón, INE, CNMC, geoportal de gasolineras y
NASA MODIS vía Google Earth Engine); consúltese el capítulo de datos de la
memoria para su origen y año de referencia.

## Cita

Viñals, R. (2026). *Localización óptima de puntos de recarga ultrarrápida
para vehículo eléctrico en Aragón: modelo Life Freesve* [código].
GitHub. https://github.com/USUARIO/tfm-recarga-aragon

## Licencia

Publicado bajo licencia MIT (véase el archivo `LICENSE`).
