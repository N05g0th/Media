#!/usr/bin/env python3
"""
Busca archivos de películas duplicados en la carpeta donde se encuentra
este script, comparando solo el nombre y el año (ignorando resolución,
idioma, extensión, etc.)

Ejemplo:
  "A Rainy Day in New York (2019) [720p] [DUAL].mkv"
  "A Rainy Day in New York (2019) [1080p] [LATINO].mp4"
  -> Se consideran la misma película: "A Rainy Day in New York (2019)"
"""

import os
import re
from collections import defaultdict

# Extensiones de video/audio que se van a considerar como "películas"
EXTENSIONES_VALIDAS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv",
    ".m4v", ".mpg", ".mpeg", ".webm", ".mp3"
}

# Captura todo hasta el cierre del paréntesis que contiene el año (####)
PATRON_TITULO_ANIO = re.compile(r"^(.*?\(\d{4}\))")


def obtener_clave(nombre_archivo):
    """
    Extrae 'Nombre (Año)' de un nombre de archivo.
    Devuelve None si no encuentra el patrón.
    """
    nombre_sin_ext, _ = os.path.splitext(nombre_archivo)
    match = PATRON_TITULO_ANIO.search(nombre_sin_ext)
    if match:
        return match.group(1).strip()
    return None


def buscar_duplicados(carpeta):
    archivos_por_clave = defaultdict(list)

    for nombre_archivo in os.listdir(carpeta):
        ruta_completa = os.path.join(carpeta, nombre_archivo)

        if not os.path.isfile(ruta_completa):
            continue

        _, extension = os.path.splitext(nombre_archivo)
        if extension.lower() not in EXTENSIONES_VALIDAS:
            continue

        clave = obtener_clave(nombre_archivo)
        if clave is None:
            print(f"[AVISO] No se pudo extraer 'Nombre (Año)' de: {nombre_archivo}")
            continue

        archivos_por_clave[clave].append(nombre_archivo)

    return archivos_por_clave


def guardar_reporte(carpeta, duplicados):
    """
    Genera un archivo de texto con el listado (en orden alfabético) de todos
    los archivos individuales que resultaron duplicados.
    """
    ruta_salida = os.path.join(carpeta, "peliculas_duplicadas.txt")

    # Junta todos los archivos duplicados en una sola lista y los ordena
    todos_los_archivos = []
    for archivos in duplicados.values():
        todos_los_archivos.extend(archivos)
    todos_los_archivos.sort(key=str.lower)

    with open(ruta_salida, "w", encoding="utf-8") as f:
        f.write("Listado de archivos duplicados (orden alfabético)\n")
        f.write("=" * 50 + "\n\n")
        for archivo in todos_los_archivos:
            f.write(f"{archivo}\n")

    return ruta_salida


def main():
    carpeta = os.path.dirname(os.path.abspath(__file__))
    print(f"Buscando películas duplicadas en: {carpeta}\n")

    resultados = buscar_duplicados(carpeta)
    duplicados = {clave: archivos for clave, archivos in resultados.items() if len(archivos) > 1}

    if not duplicados:
        print("No se encontraron películas duplicadas.")
        return

    print(f"Se encontraron {len(duplicados)} película(s) con duplicados:\n")
    for clave, archivos in duplicados.items():
        print(f"'{clave}' -> {len(archivos)} copias:")
        for archivo in archivos:
            print(f"   - {archivo}")
        print()

    ruta_salida = guardar_reporte(carpeta, duplicados)
    print(f"Se generó el archivo con el listado: {ruta_salida}")


if __name__ == "__main__":
    main()