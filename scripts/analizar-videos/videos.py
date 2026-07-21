#!/usr/bin/env python3
"""
analizar_m3u.py
----------------
Lee una lista M3U (por defecto "entrada.m3u"), analiza cada enlace de video
con ffprobe (parte de FFmpeg) para detectar:

  - Calidad de video: 480p, 720p, 1080p, 4K
  - Idioma(s) de audio: ENG, ESP, FRA, etc.
  - Si el video tiene más de un audio, se marca como DUAL

...y agrega esa info entre corchetes AL FINAL del título de cada entrada, por ejemplo:

    #EXTINF:-1,Nombre Pelicula (2026) [4K] [DUAL]
    http://ejemplo.com/video.mp4

    #EXTINF:-1,Otra pelicula [720p] [ENG]
    http://ejemplo.com/video2.mp4

Si el título ya trae info de calidad (ej. "1080p") o de audio (ej. "DUAL",
"LATINO", "ENG", etc.) el script no vuelve a agregar ese tag para no duplicar.

REQUISITOS
----------
- Python 3.8+
- FFmpeg/ffprobe instalado y accesible en el PATH
    Windows:  https://ffmpeg.org/download.html
    macOS:    brew install ffmpeg
    Linux:    sudo apt install ffmpeg   (o el gestor de paquetes que uses)

USO
---
    python analizar_m3u.py
    python analizar_m3u.py -i entrada.m3u -o salida.m3u
    python analizar_m3u.py -i entrada.m3u -o salida.m3u --timeout 20 --workers 4

NOTAS
-----
- Los enlaces remotos (streams online) se analizan leyendo solo la cabecera
  del archivo, por lo que ffprobe no descarga el video completo, pero igual
  puede tardar unos segundos por enlace según la velocidad de la conexión.
- Si ffprobe no logra analizar un enlace (caído, protegido, timeout, etc.)
  el título se deja igual y se agrega [ERROR] para que puedas revisarlo.
- Podés correr el análisis en paralelo con --workers para acelerar listas
  grandes (cuidado con saturar el servidor de origen o tu propia conexión).
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Optional

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


@dataclass
class Entrada:
    extinf_extra: str          # atributos tras #EXTINF:-1  (duración, tvg-id, etc. si los hay)
    titulo: str                 # título original
    url: str                    # enlace del video
    lineas_previas: List[str] = field(default_factory=list)  # otras líneas (#EXTGRP, #EXTVLCOPT, etc.)
    error_detalle: Optional[str] = None  # motivo del error, si lo hubo (solo para consola)


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
            # otras directivas (#EXTGRP, #EXTVLCOPT, #EXTALB, etc.)
            buffer_previas.append(linea)
        else:
            # es la URL del stream
            if extinf_actual is not None:
                # separar "#EXTINF:-1 attrs,Titulo"
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


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


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
        # formatos típicos: #EXTVLCOPT:http-user-agent=xxx  /  #EXTVLCOPT:http-referrer=xxx
        m = re.match(r"#EXTVLCOPT:http-user-agent=(.*)", l, re.IGNORECASE)
        if m:
            user_agent = m.group(1).strip()
            continue
        m = re.match(r"#EXTVLCOPT:http-referrer=(.*)", l, re.IGNORECASE)
        if m:
            headers["Referer"] = m.group(1).strip()
            continue
        # formato alternativo usado por algunas listas: #EXTHTTP:{"cookie":"..."}
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
        "-analyzeduration", "15000000",   # 15s de análisis (streams IPTV tardan en mandar metadata)
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


def procesar_entrada(entrada: Entrada, timeout: int, debug: bool = False) -> Entrada:
    info = analizar_video(entrada.url, timeout, entrada.lineas_previas, debug=debug)

    if info.get("error"):
        entrada.error_detalle = info["error"]  # type: ignore[attr-defined]
        return entrada

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

    return entrada


def escribir_m3u(entradas: List[Entrada], ruta_salida: str):
    with open(ruta_salida, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for e in entradas:
            for previa in e.lineas_previas:
                f.write(previa + "\n")
            f.write(f"#EXTINF:-1{e.extinf_extra},{e.titulo}\n")
            f.write(f"{e.url}\n")


def main():
    parser = argparse.ArgumentParser(description="Analiza y etiqueta calidad/idioma en una lista M3U")
    parser.add_argument("-i", "--input", default="entrada.m3u", help="Archivo M3U de entrada (default: entrada.m3u)")
    parser.add_argument("-o", "--output", default="salida.m3u", help="Archivo M3U de salida (default: salida.m3u)")
    parser.add_argument("--timeout", type=int, default=25, help="Timeout en segundos por enlace (default: 25)")
    parser.add_argument("--workers", type=int, default=4, help="Análisis en paralelo (default: 4)")
    parser.add_argument("--debug", action="store_true", help="Muestra el error real que devuelve ffprobe por cada enlace fallido")
    args = parser.parse_args()

    verificar_ffprobe()

    print(f"Leyendo '{args.input}'...")
    entradas = parsear_m3u(args.input)
    total = len(entradas)
    print(f"Se encontraron {total} elementos. Analizando con {args.workers} hilo(s)...\n")

    resultados: List[Entrada] = [None] * total  # type: ignore

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futuros = {
            executor.submit(procesar_entrada, e, args.timeout, args.debug): idx
            for idx, e in enumerate(entradas)
        }
        completados = 0
        errores = 0
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
                errores += 1
                print(f"    -> motivo: {r.error_detalle}")

    escribir_m3u(resultados, args.output)
    print(f"\nListo. Archivo generado: {args.output}")
    if errores:
        print(
            f"{errores} de {total} enlace(s) no se pudieron analizar. "
            f"Corré de nuevo con --debug para ver el detalle de ffprobe, "
            f"o probá subir --timeout si tu conexión/servidor es lento."
        )


if __name__ == "__main__":
    main()
