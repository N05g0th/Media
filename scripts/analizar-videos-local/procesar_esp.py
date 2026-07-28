#!/usr/bin/env python3
"""
Renombra archivos de películas al formato:
    Nombre de la Película (Año) [calidad] [audio].ext

- Busca el nombre en español (México) y el año usando la API de TMDB
  (si no hay título traducido, usa el título en inglés como respaldo).
- Analiza el archivo de video con ffprobe para detectar la resolución
  (calidad) y los idiomas de audio disponibles.
- Si el video tiene más de una pista de audio, usa la etiqueta [DUAL]
  en vez de listar cada idioma.

Requisitos:
    pip install requests
    ffmpeg / ffprobe instalado y disponible en el PATH del sistema
    (en Windows: https://ffmpeg.org/download.html, agregarlo al PATH)

Uso:
    # Modo simulación (no renombra nada, solo muestra qué haría):
    python renombrar_peliculas.py "C:\\ruta\\a\\la\\carpeta"

    # Modo real (aplica los cambios):
    python renombrar_peliculas.py "C:\\ruta\\a\\la\\carpeta" --aplicar
"""

import os
import re
import json
import subprocess
import argparse
import requests

# ⚠️ Esta es tu API key de TMDB. Al ser un script local no hay mayor
# problema, pero evita subir este archivo a repositorios públicos (GitHub, etc.)
# con la key incluida.
TMDB_API_KEY = "6f6ac958e9e94c4c42371ebba58f4e00"
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".m4v"}


# --------------------------------------------------------------------------
# Limpieza del nombre original del archivo (quita tags, calidad, año, etc.)
# --------------------------------------------------------------------------
def limpiar_nombre(nombre_archivo):
    nombre, _ = os.path.splitext(nombre_archivo)

    year_match = re.search(r"(19|20)\d{2}", nombre)
    year = year_match.group(0) if year_match else None

    patron_corte = (
        r"(19|20)\d{2}|1080p|720p|2160p|480p|4k|BluRay|WEB-?DL|WEBRip|"
        r"HDRip|DVDRip|x264|x265|HEVC|AAC|AC3|DTS|DUAL|LATINO|CASTELLANO|"
        r"SUBTITULADO|SUB|\[|\("
    )
    corte = re.split(patron_corte, nombre, flags=re.IGNORECASE)[0]
    corte = corte.replace(".", " ").replace("_", " ").strip(" -_.")
    return corte, year


# --------------------------------------------------------------------------
# Búsqueda en TMDB
# --------------------------------------------------------------------------
def buscar_en_tmdb(nombre, year=None):
    params = {
        "api_key": TMDB_API_KEY,
        "query": nombre,
        "language": "es-MX",
    }
    if year:
        params["year"] = year

    try:
        resp = requests.get(TMDB_SEARCH_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        resultados = data.get("results", [])
        if not resultados:
            return None, None

        mejor = resultados[0]
        titulo = mejor.get("title")
        fecha = mejor.get("release_date", "")
        anio = fecha.split("-")[0] if fecha else year

        # Si TMDB no tiene título traducido al español para esta película,
        # "title" puede venir vacío; en ese caso se intenta de nuevo en
        # inglés como respaldo para no perder la película.
        if not titulo:
            params_fallback = dict(params)
            params_fallback["language"] = "en-US"
            resp_fallback = requests.get(TMDB_SEARCH_URL, params=params_fallback, timeout=10)
            resp_fallback.raise_for_status()
            data_fallback = resp_fallback.json()
            resultados_fallback = data_fallback.get("results", [])
            if resultados_fallback:
                titulo = resultados_fallback[0].get("title")

        return titulo, anio
    except requests.RequestException as e:
        print(f"  ⚠ Error consultando TMDB: {e}")
        return None, None


# --------------------------------------------------------------------------
# Análisis del video con ffprobe
# --------------------------------------------------------------------------
def analizar_video(ruta_archivo):
    """Devuelve (calidad, lista_idiomas_audio) usando ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", ruta_archivo,
    ]
    try:
        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        info = json.loads(resultado.stdout)
    except FileNotFoundError:
        print("  ⚠ ffprobe no está instalado o no está en el PATH.")
        return None, []
    except (subprocess.SubprocessError, json.JSONDecodeError) as e:
        print(f"  ⚠ No se pudo analizar el video: {e}")
        return None, []

    calidad = None
    audios = []

    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video" and calidad is None:
            alto = stream.get("height")
            if alto:
                calidad = mapear_calidad(alto)
        elif stream.get("codec_type") == "audio":
            idioma = stream.get("tags", {}).get("language", "und")
            audios.append(idioma.upper())

    return calidad, audios


def mapear_calidad(alto):
    if alto >= 2000:
        return "2160p"
    elif alto >= 1000:
        return "1080p"
    elif alto >= 700:
        return "720p"
    elif alto >= 470:
        return "480p"
    else:
        return f"{alto}p"


def formatear_audio(lista_idiomas):
    if not lista_idiomas:
        return None
    if len(lista_idiomas) > 1:
        return "DUAL"

    idioma = lista_idiomas[0]
    mapa = {"ENG": "ENG", "EN": "ENG", "SPA": "LAT", "ES": "LAT", "UND": "UND"}
    return mapa.get(idioma, idioma)


# --------------------------------------------------------------------------
# Proceso principal
# --------------------------------------------------------------------------
def procesar_carpeta(carpeta, simular=True):
    archivos = [
        f for f in os.listdir(carpeta)
        if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS
    ]

    if not archivos:
        print("No se encontraron archivos de video en la carpeta.")
        return

    if simular:
        print("=== MODO SIMULACIÓN (no se renombrará nada) ===\n")

    for archivo in archivos:
        ruta = os.path.join(carpeta, archivo)
        print(f"Procesando: {archivo}")

        nombre_limpio, year = limpiar_nombre(archivo)
        titulo, anio = buscar_en_tmdb(nombre_limpio, year)

        if not titulo:
            print("  ⚠ No se encontró en TMDB, se omite.\n")
            continue

        calidad, audios = analizar_video(ruta)
        etiqueta_audio = formatear_audio(audios)

        partes = [f"{titulo} ({anio})" if anio else titulo]
        if calidad:
            partes.append(f"[{calidad}]")
        if etiqueta_audio:
            partes.append(f"[{etiqueta_audio}]")

        extension = os.path.splitext(archivo)[1]
        nuevo_nombre = " ".join(partes) + extension
        nuevo_nombre = re.sub(r'[<>:"/\\|?*]', "", nuevo_nombre)  # caracteres inválidos

        nueva_ruta = os.path.join(carpeta, nuevo_nombre)
        print(f"  → Nuevo nombre: {nuevo_nombre}")

        if not simular:
            if os.path.exists(nueva_ruta):
                print("  ⚠ Ya existe un archivo con ese nombre, se omite.")
            else:
                os.rename(ruta, nueva_ruta)
                print("  ✔ Renombrado.")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Renombra películas usando TMDB y ffprobe."
    )
    parser.add_argument(
        "carpeta",
        nargs="?",
        default=None,
        help="Ruta a la carpeta con los archivos de video. "
             "Si no se indica, usa la misma carpeta donde está este script.",
    )
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="Aplica los cambios de verdad (sin esta bandera, solo se simula)",
    )
    args = parser.parse_args()

    carpeta = args.carpeta or os.path.dirname(os.path.abspath(__file__))

    if not os.path.isdir(carpeta):
        print("La carpeta indicada no existe.")
        return

    print(f"Carpeta a procesar: {carpeta}\n")
    procesar_carpeta(carpeta, simular=not args.aplicar)


if __name__ == "__main__":
    main()