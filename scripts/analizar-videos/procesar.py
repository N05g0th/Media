#!/usr/bin/env python3
"""
procesar_m3u.py
----------------
Combina en un solo paso lo que antes hacían dos scripts separados:

  1) Analiza cada enlace de video con ffprobe (FFmpeg) para detectar:
       - Calidad de video: 480p, 720p, 1080p, 4K
       - Idioma(s) de audio: ENG, ESP, FRA, etc. (o DUAL si hay más de uno)
     ...y agrega esa info entre corchetes AL FINAL del título:

         #EXTINF:-1,Nombre Pelicula (2026) [4K] [DUAL]

     Si el título ya trae esa info (ej. "1080p", "DUAL", "LATINO", "ENG")
     no se vuelve a agregar, para no duplicar.
     Si un enlace falla, el título se deja intacto (no se agrega [ERROR],
     pero el motivo se imprime en consola para que lo puedas revisar).

  2) Busca cada título en The Movie Database (TMDB), y agrega/actualiza
     en la misma línea #EXTINF los atributos:
         group-title="<Género>"
         tvg-logo="<URL del póster>"

Resultado: una sola pasada sobre 'entrada.m3u' que genera 'salida.m3u'
con calidad + idioma en el título, y género + póster como atributos.

REQUISITOS
----------
- Python 3.8+
- pip install requests
- FFmpeg/ffprobe instalado y accesible en el PATH
    Windows:  https://ffmpeg.org/download.html
    macOS:    brew install ffmpeg
    Linux:    sudo apt install ffmpeg   (o el gestor de paquetes que uses)

USO
---
    python procesar_m3u.py
    python procesar_m3u.py -i entrada.m3u -o salida.m3u
    python procesar_m3u.py -i entrada.m3u -o salida.m3u --timeout 20 --workers 4 --debug

NOTAS
-----
- El análisis de video (ffprobe) corre en paralelo entre varias entradas
  (--workers) para ir más rápido.
- Las búsquedas a TMDB se hacen de forma serializada (con una pequeña
  pausa entre cada una, --tmdb-pause) para no saturar/exceder límites
  de la API, aunque el resto de cada entrada (ffprobe) siga en paralelo.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Optional

import requests

# ------------------------------------------------------------------ #
# Configuración TMDB
# ------------------------------------------------------------------ #
TMDB_API_KEY = "6f6ac958e9e94c4c42371ebba58f4e00"
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_GENRE_URL = "https://api.themoviedb.org/3/genre/movie/list"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"  # tamaño del póster

# Géneros que NO se deben usar como group-title, aunque la película los tenga
GENEROS_EXCLUIDOS = {"Bélica", "Familia", "Misterio", "Música", "Historia", "Crimen"}

# Lock para serializar las llamadas a TMDB (evita saturar/exceder límites de la API)
_TMDB_LOCK = threading.Lock()

# ------------------------------------------------------------------ #
# Configuración de mapeo de idiomas (código ISO 639-2 -> etiqueta)
# ------------------------------------------------------------------ #
LANG_MAP = {
    "eng": "ENG", "en": "ENG",
    "spa": "ESP", "es": "ESP", "lat": "ESP", "es-419": "ESP",
    "fre": "FRA", "fra": "FRA", "fr": "FRA",
    "ger": "ALE", "deu": "ALE", "de": "ALE",
    "ita": "ITA", "it": "ITA",
    "por": "POR", "pt": "POR",
    "jpn": "JAP", "ja": "JAP",
    "kor": "KOR", "ko": "KOR",
    "chi": "CHI", "zho": "CHI", "zh": "CHI",
    "rus": "RUS", "ru": "RUS",
    "ara": "ARA", "ar": "ARA",
    "und": "UND",  # idioma no especificado en los metadatos
}

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class Entrada:
    extinf_extra: str          # atributos tras #EXTINF:-1 (tvg-id, group-title, etc. si ya venían)
    titulo: str                 # título original
    url: str                    # enlace del video
    lineas_previas: List[str] = field(default_factory=list)  # #EXTGRP, #EXTVLCOPT, etc.
    error_detalle: Optional[str] = None   # motivo del error de ffprobe, si lo hubo (solo consola)
    tmdb_error: Optional[str] = None      # motivo del error de TMDB, si lo hubo (solo consola)


# ------------------------------------------------------------------ #
# Lectura / escritura del M3U
# ------------------------------------------------------------------ #
def verificar_ffprobe():
    if shutil.which("ffprobe") is None:
        sys.exit(
            "ERROR: no se encontró 'ffprobe' en el PATH.\n"
            "Instalá FFmpeg (incluye ffprobe) y volvé a intentar.\n"
            "Más info: https://ffmpeg.org/download.html"
        )


def parsear_m3u(ruta: str) -> List[Entrada]:
    with open(ruta, "r", encoding="utf-8", errors="ignore") as f:
        lineas = [l.rstrip("\n") for l in f]

    entradas: List[Entrada] = []
    buffer_previas: List[str] = []
    extinf_actual: Optional[str] = None

    for linea in lineas:
        if not linea.strip():
            continue
        if linea.strip() == "#EXTM3U":
            continue

        if linea.startswith("#EXTINF"):
            extinf_actual = linea
        elif linea.startswith("#"):
            buffer_previas.append(linea)
        else:
            if extinf_actual is not None:
                m = re.match(r"#EXTINF:(-?\d+)(.*?),(.*)", extinf_actual)
                if m:
                    extra = m.group(2)  # atributos tvg-id="" tvg-logo="" group-title="" etc.
                    titulo = m.group(3)
                else:
                    extra = ""
                    titulo = extinf_actual.split(",", 1)[-1] if "," in extinf_actual else ""

                entradas.append(Entrada(
                    extinf_extra=extra,
                    titulo=titulo.strip(),
                    url=linea.strip(),
                    lineas_previas=buffer_previas,
                ))
            extinf_actual = None
            buffer_previas = []

    return entradas


def escribir_m3u(entradas: List[Entrada], ruta_salida: str):
    with open(ruta_salida, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for e in entradas:
            for previa in e.lineas_previas:
                f.write(previa + "\n")
            f.write(f"#EXTINF:-1{e.extinf_extra},{e.titulo}\n")
            f.write(f"{e.url}\n")


# ------------------------------------------------------------------ #
# Parte 1: calidad de video / idioma de audio (ffprobe)
# ------------------------------------------------------------------ #
def clasificar_calidad(alto: int) -> str:
    if alto >= 2160:
        return "4K"
    elif alto >= 1080:
        return "1080p"
    elif alto >= 720:
        return "720p"
    elif alto >= 480:
        return "480p"
    elif alto > 0:
        return f"{alto}p"
    return "SD"


def extraer_headers(lineas_previas: List[str]) -> dict:
    """
    Busca directivas #EXTVLCOPT (u otras comunes en listas IPTV) para
    reutilizar user-agent / referer / cookie al analizar el enlace,
    ya que muchos servidores devuelven error o cierran la conexión
    si no reciben estos headers.
    """
    user_agent = DEFAULT_USER_AGENT
    headers = {}

    for linea in lineas_previas:
        l = linea.strip()
        m = re.match(r"#EXTVLCOPT:http-user-agent=(.*)", l, re.IGNORECASE)
        if m:
            user_agent = m.group(1).strip()
            continue
        m = re.match(r"#EXTVLCOPT:http-referrer=(.*)", l, re.IGNORECASE)
        if m:
            headers["Referer"] = m.group(1).strip()
            continue
        m = re.match(r"#EXTHTTP:(.*)", l, re.IGNORECASE)
        if m:
            try:
                extra = json.loads(m.group(1))
                for k, v in extra.items():
                    headers[k.capitalize()] = v
            except json.JSONDecodeError:
                pass

    return {"user_agent": user_agent, "headers": headers}


def analizar_video(url: str, timeout: int, lineas_previas: List[str], debug: bool = False) -> dict:
    """
    Ejecuta ffprobe sobre la URL y devuelve un dict con:
        { "calidad": str, "idiomas": [str, ...], "error": Optional[str] }
    """
    hdrs = extraer_headers(lineas_previas)

    cmd = [
        "ffprobe",
        "-v", "error",
        "-print_format", "json",
        "-show_streams",
        "-analyzeduration", "15000000",
        "-probesize", "15000000",
        "-user_agent", hdrs["user_agent"],
    ]

    if hdrs["headers"]:
        headers_str = "".join(f"{k}: {v}\r\n" for k, v in hdrs["headers"].items())
        cmd += ["-headers", headers_str]

    cmd += [url]

    try:
        resultado = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return {"calidad": None, "idiomas": [], "error": "timeout"}
    except Exception as e:
        return {"calidad": None, "idiomas": [], "error": str(e)}

    if debug and resultado.stderr.strip():
        print(f"    [debug] ffprobe stderr: {resultado.stderr.strip()[:300]}")

    if resultado.returncode != 0 or not resultado.stdout.strip():
        motivo = resultado.stderr.strip().splitlines()[-1] if resultado.stderr.strip() else "sin salida de ffprobe"
        return {"calidad": None, "idiomas": [], "error": motivo}

    try:
        data = json.loads(resultado.stdout)
    except json.JSONDecodeError:
        return {"calidad": None, "idiomas": [], "error": "json inválido"}

    streams = data.get("streams", [])
    calidad = None
    idiomas: List[str] = []

    for s in streams:
        if s.get("codec_type") == "video" and calidad is None:
            alto = s.get("height") or 0
            calidad = clasificar_calidad(int(alto))
        elif s.get("codec_type") == "audio":
            lang_code = (s.get("tags", {}) or {}).get("language", "und").lower()
            etiqueta = LANG_MAP.get(lang_code, lang_code.upper() if lang_code else "UND")
            if etiqueta not in idiomas:
                idiomas.append(etiqueta)

    if calidad is None and not idiomas:
        return {"calidad": None, "idiomas": [], "error": "sin streams detectados"}

    return {"calidad": calidad or "SD", "idiomas": idiomas, "error": None}


# Palabras que, si ya aparecen en el título, indican que el audio/idioma
# ya está identificado manualmente y no hace falta que el script lo agregue.
PALABRAS_AUDIO_EXISTENTE = set(LANG_MAP.values()) | {
    "DUAL", "LATINO", "CASTELLANO", "ESPAÑOL", "ESPANOL",
    "INGLES", "INGLÉS", "SUBTITULADO", "SUBS", "SUB", "VOSE", "MULTI",
}
_PATRON_AUDIO_EXISTENTE = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in sorted(PALABRAS_AUDIO_EXISTENTE, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_PATRON_CALIDAD_EXISTENTE = re.compile(
    r"\b(4K|2160p|1080p|720p|480p|360p|240p)\b", re.IGNORECASE
)


def titulo_ya_tiene_calidad(titulo: str) -> bool:
    return bool(_PATRON_CALIDAD_EXISTENTE.search(titulo))


def titulo_ya_tiene_audio(titulo: str) -> bool:
    return bool(_PATRON_AUDIO_EXISTENTE.search(titulo))


def aplicar_tags_calidad_audio(entrada: Entrada, info: dict):
    """Agrega [calidad] y/o [ENG]/[DUAL] al final del título, sin duplicar lo ya existente."""
    partes = []

    if not titulo_ya_tiene_calidad(entrada.titulo) and info.get("calidad"):
        partes.append(f"[{info['calidad']}]")

    if not titulo_ya_tiene_audio(entrada.titulo):
        idiomas = info.get("idiomas") or []
        if len(idiomas) > 1:
            partes.append("[DUAL]")
        elif len(idiomas) == 1:
            partes.append(f"[{idiomas[0]}]")

    if partes:
        entrada.titulo = f"{entrada.titulo.rstrip()} {' '.join(partes)}".strip()


# ------------------------------------------------------------------ #
# Parte 2: género / póster (TMDB)
# ------------------------------------------------------------------ #
def obtener_generos(idioma: str) -> dict:
    """Descarga el catálogo de géneros de TMDB (id -> nombre)."""
    resp = requests.get(
        TMDB_GENRE_URL,
        params={"api_key": TMDB_API_KEY, "language": idioma},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return {g["id"]: g["name"] for g in data["genres"]}


def limpiar_titulo_busqueda(titulo_original: str) -> str:
    """Quita año entre paréntesis, corchetes de calidad/audio, etc, para mejorar la búsqueda."""
    titulo = re.sub(r"\(\d{4}\)", "", titulo_original)
    titulo = re.sub(r"\[.*?\]", "", titulo)
    titulo = re.sub(r"\s{2,}", " ", titulo)
    return titulo.strip()


def buscar_pelicula(titulo: str, mapa_generos: dict, idioma: str, pausa: float) -> dict:
    """
    Busca la película en TMDB (serializado con un lock para no saturar la API)
    y devuelve { "genero": str, "poster_url": Optional[str], "error": Optional[str] }.
    """
    with _TMDB_LOCK:
        try:
            resp = requests.get(
                TMDB_SEARCH_URL,
                params={"api_key": TMDB_API_KEY, "query": titulo, "language": idioma},
                timeout=10,
            )
            resp.raise_for_status()
            resultados = resp.json().get("results", [])

            if not resultados:
                return {"genero": "Sin clasificar", "poster_url": None, "error": None}

            pelicula = resultados[0]

            ids_genero = pelicula.get("genre_ids", [])
            nombres_genero = [mapa_generos.get(gid, "Desconocido") for gid in ids_genero]
            nombres_validos = [n for n in nombres_genero if n not in GENEROS_EXCLUIDOS]

            if not nombres_genero:
                genero = "Sin género"
            elif nombres_validos:
                genero = nombres_validos[0]
            else:
                genero = "Sin género"

            poster_path = pelicula.get("poster_path")
            poster_url = f"{TMDB_IMAGE_BASE_URL}{poster_path}" if poster_path else None

            return {"genero": genero, "poster_url": poster_url, "error": None}
        except requests.RequestException as e:
            return {"genero": "Error de búsqueda", "poster_url": None, "error": str(e)}
        finally:
            time.sleep(pausa)


def _insertar_atributo(extra: str, nombre_atributo: str, valor: Optional[str]) -> str:
    """Inserta o reemplaza un atributo (ej. group-title, tvg-logo) en la parte de atributos del EXTINF."""
    if not valor:
        return extra

    patron = rf'{nombre_atributo}="[^"]*"'
    if re.search(patron, extra):
        return re.sub(patron, f'{nombre_atributo}="{valor}"', extra)

    extra = extra.rstrip()
    return f'{extra} {nombre_atributo}="{valor}"' if extra else f' {nombre_atributo}="{valor}"'


def aplicar_genero_poster(entrada: Entrada, genero: Optional[str], poster_url: Optional[str]):
    entrada.extinf_extra = _insertar_atributo(entrada.extinf_extra, "group-title", genero)
    entrada.extinf_extra = _insertar_atributo(entrada.extinf_extra, "tvg-logo", poster_url)


# ------------------------------------------------------------------ #
# Procesamiento combinado por entrada
# ------------------------------------------------------------------ #
def procesar_entrada(entrada: Entrada, mapa_generos: dict, args) -> Entrada:
    # 1) Calidad / idioma de audio vía ffprobe
    info_video = analizar_video(entrada.url, args.timeout, entrada.lineas_previas, debug=args.debug)
    if info_video.get("error"):
        entrada.error_detalle = info_video["error"]
    else:
        aplicar_tags_calidad_audio(entrada, info_video)

    # 2) Género / póster vía TMDB (usa el título limpio, sin tags de calidad/audio)
    titulo_busqueda = limpiar_titulo_busqueda(entrada.titulo)
    resultado_tmdb = buscar_pelicula(titulo_busqueda, mapa_generos, args.idioma, args.tmdb_pause)
    if resultado_tmdb.get("error"):
        entrada.tmdb_error = resultado_tmdb["error"]
    aplicar_genero_poster(entrada, resultado_tmdb.get("genero"), resultado_tmdb.get("poster_url"))

    return entrada


# ------------------------------------------------------------------ #
# Programa principal
# ------------------------------------------------------------------ #
def main():
    parser = argparse.ArgumentParser(
        description="Analiza calidad/audio (ffprobe) y agrega género/póster (TMDB) en una lista M3U"
    )
    parser.add_argument("-i", "--input", default="entrada.m3u", help="Archivo M3U de entrada (default: entrada.m3u)")
    parser.add_argument("-o", "--output", default="salida.m3u", help="Archivo M3U de salida (default: salida.m3u)")
    parser.add_argument("--timeout", type=int, default=25, help="Timeout en segundos por enlace para ffprobe (default: 25)")
    parser.add_argument("--workers", type=int, default=4, help="Entradas procesadas en paralelo (default: 4)")
    parser.add_argument("--debug", action="store_true", help="Muestra el error real de ffprobe por cada enlace fallido")
    parser.add_argument("--idioma", default="es-MX", help="Idioma para nombres de género y resultados de TMDB (default: es-MX)")
    parser.add_argument("--tmdb-pause", type=float, default=0.25, help="Pausa en segundos entre peticiones a TMDB (default: 0.25)")
    args = parser.parse_args()

    verificar_ffprobe()

    print("Obteniendo catálogo de géneros de TMDB...")
    mapa_generos = obtener_generos(args.idioma)

    print(f"Leyendo '{args.input}'...")
    entradas = parsear_m3u(args.input)
    total = len(entradas)
    print(f"Se encontraron {total} entradas. Procesando con {args.workers} hilo(s)...\n")

    resultados: List[Entrada] = [None] * total  # type: ignore

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futuros = {
            executor.submit(procesar_entrada, e, mapa_generos, args): idx
            for idx, e in enumerate(entradas)
        }
        completados = 0
        errores_video = 0
        errores_tmdb = 0
        for fut in as_completed(futuros):
            idx = futuros[fut]
            completados += 1
            try:
                resultados[idx] = fut.result()
            except Exception as exc:
                entradas[idx].error_detalle = str(exc)
                resultados[idx] = entradas[idx]

            r = resultados[idx]
            print(f"[{completados}/{total}] {r.titulo}")
            if r.error_detalle:
                errores_video += 1
                print(f"    -> ffprobe: {r.error_detalle}")
            if r.tmdb_error:
                errores_tmdb += 1
                print(f"    -> TMDB: {r.tmdb_error}")

    escribir_m3u(resultados, args.output)
    print(f"\nListo. Archivo generado: {args.output}")

    if errores_video:
        print(
            f"{errores_video} de {total} enlace(s) no se pudieron analizar con ffprobe "
            f"(el título se dejó sin cambios en esos casos). Corré con --debug para más detalle."
        )
    if errores_tmdb:
        print(f"{errores_tmdb} de {total} búsqueda(s) en TMDB fallaron.")


if __name__ == "__main__":
    main()
