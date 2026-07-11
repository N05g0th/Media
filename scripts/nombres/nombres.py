#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
renombrar_m3u_tmdb.py

Lee una lista M3U, busca cada título en TMDB (idioma es-MX) y reescribe
el título de cada #EXTINF con el formato:

    Nombre (año) [Etiqueta1] [Etiqueta2]

Las etiquetas originales entre corchetes (p. ej. [Dual], [Eng]) se
conservan y se colocan al final del título nuevo.

Uso:
    python renombrar_m3u_tmdb.py
    python renombrar_m3u_tmdb.py --entrada origen.m3u --salida salida.m3u
    python renombrar_m3u_tmdb.py --api-key TU_API_KEY

Requiere:
    pip install requests
"""

import argparse
import re
import sys
import time
import unicodedata
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Falta la librería 'requests'. Instálala con: pip install requests")

TMDB_API_KEY_DEFAULT = "6f6ac958e9e94c4c42371ebba58f4e00"
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"

TAG_RE = re.compile(r"\[([^\]]+)\]")
YEAR_RE = re.compile(r"\((\d{4})\)")
EXTINF_RE = re.compile(r"^#EXTINF:(-?\d+)\s*,(.*)$")


def quitar_acentos(texto):
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def limpiar_titulo(titulo_crudo):
    """Quita etiquetas [Dual]/[Eng]/etc. y el año entre paréntesis para
    obtener una consulta de búsqueda limpia. Devuelve también el año
    (si estaba) y la lista de etiquetas originales, en el orden en que
    aparecían, para poder regresarlas al título final."""
    etiquetas = TAG_RE.findall(titulo_crudo)
    titulo = TAG_RE.sub("", titulo_crudo)
    anio_pista = None
    m = YEAR_RE.search(titulo)
    if m:
        anio_pista = m.group(1)
        titulo = titulo.replace(m.group(0), "")
    titulo = re.sub(r"\(\s*\)", "", titulo)
    titulo = re.sub(r"\s{2,}", " ", titulo).strip(" -:")
    return titulo, anio_pista, etiquetas


def parsear_m3u(ruta):
    """Devuelve una lista de dicts: {extinf_dur, titulo_crudo, url, extra_lineas}"""
    lineas = ruta.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    entradas = []
    cabecera = []
    i = 0
    # conserva la cabecera (#EXTM3U y comentarios previos al primer EXTINF)
    while i < len(lineas) and not lineas[i].strip().startswith("#EXTINF"):
        if lineas[i].strip():
            cabecera.append(lineas[i])
        i += 1

    while i < len(lineas):
        linea = lineas[i].strip()
        if linea.startswith("#EXTINF"):
            match = EXTINF_RE.match(linea)
            duracion = match.group(1) if match else "-1"
            titulo_crudo = match.group(2).strip() if match else ""
            j = i + 1
            while j < len(lineas) and lineas[j].strip() == "":
                j += 1
            url = lineas[j].strip() if j < len(lineas) else ""
            entradas.append({
                "duracion": duracion,
                "titulo_crudo": titulo_crudo,
                "url": url,
            })
            i = j + 1
        else:
            i += 1
    return cabecera, entradas


def buscar_en_tmdb(sesion, api_key, titulo, anio_pista, reintentos=3):
    """Busca en TMDB (es-MX). Devuelve (titulo_es, anio) o (None, None)."""

    def consulta(con_anio):
        params = {
            "api_key": api_key,
            "language": "es-MX",
            "include_adult": "false",
            "query": titulo,
        }
        if con_anio and anio_pista:
            params["year"] = anio_pista
        for intento in range(reintentos):
            try:
                r = sesion.get(TMDB_SEARCH_URL, params=params, timeout=15)
            except requests.RequestException:
                time.sleep(1.5 * (intento + 1))
                continue
            if r.status_code == 429:
                espera = float(r.headers.get("Retry-After", "1"))
                time.sleep(espera + 0.5)
                continue
            if not r.ok:
                time.sleep(1 * (intento + 1))
                continue
            return r.json().get("results", [])
        return []

    resultados = consulta(con_anio=True)
    if not resultados and anio_pista:
        resultados = consulta(con_anio=False)
    if not resultados:
        return None, None

    top = resultados[0]
    titulo_es = (top.get("title") or top.get("original_title") or "").strip()
    fecha = top.get("release_date") or ""
    anio = fecha[:4] if len(fecha) >= 4 else anio_pista
    if not titulo_es:
        return None, None
    return titulo_es, anio


def formatear_titulo(titulo_es, anio, etiquetas=None):
    base = f"{titulo_es} ({anio})" if anio else titulo_es
    if etiquetas:
        sufijo = " ".join(f"[{e}]" for e in etiquetas)
        return f"{base} {sufijo}"
    return base


def main():
    ap = argparse.ArgumentParser(description="Renombra títulos de una lista M3U usando TMDB (es-MX).")
    ap.add_argument("--entrada", default="origen.m3u", help="Ruta del M3U de entrada (default: origen.m3u)")
    ap.add_argument("--salida", default="salida.m3u", help="Ruta del M3U de salida (default: salida.m3u)")
    ap.add_argument("--api-key", default=TMDB_API_KEY_DEFAULT, help="API key de TMDB (v3 auth)")
    ap.add_argument("--pausa", type=float, default=0.05, help="Pausa en segundos entre peticiones (default: 0.05)")
    ap.add_argument("--log-no-encontrados", default="no_encontrados.txt",
                     help="Archivo donde se listan los títulos que no se pudieron emparejar")
    args = ap.parse_args()

    ruta_entrada = Path(args.entrada)
    if not ruta_entrada.exists():
        sys.exit(f"No se encontró el archivo de entrada: {ruta_entrada}")

    cabecera, entradas = parsear_m3u(ruta_entrada)
    if not entradas:
        sys.exit("No se encontraron entradas #EXTINF en el archivo.")

    print(f"Leídas {len(entradas)} entradas de {ruta_entrada.name}")

    sesion = requests.Session()
    cache = {}
    no_encontrados = []
    salida_lineas = list(cabecera) if cabecera else ["#EXTM3U"]

    total = len(entradas)
    for idx, entrada in enumerate(entradas, start=1):
        titulo_crudo = entrada["titulo_crudo"]
        url = entrada["url"]
        titulo_busqueda, anio_pista, etiquetas = limpiar_titulo(titulo_crudo)

        clave = (quitar_acentos(titulo_busqueda.lower()), anio_pista)
        if clave in cache:
            titulo_es, anio = cache[clave]
        else:
            titulo_es, anio = buscar_en_tmdb(sesion, args.api_key, titulo_busqueda, anio_pista)
            cache[clave] = (titulo_es, anio)
            time.sleep(args.pausa)

        if titulo_es:
            nuevo_titulo = formatear_titulo(titulo_es, anio, etiquetas)
        else:
            nuevo_titulo = formatear_titulo(titulo_busqueda, anio_pista, etiquetas) if titulo_busqueda else titulo_crudo
            no_encontrados.append(titulo_crudo)

        salida_lineas.append(f"#EXTINF:{entrada['duracion']},{nuevo_titulo}")
        salida_lineas.append(url)

        estado = "OK " if titulo_es else "SIN COINCIDENCIA"
        print(f"[{idx}/{total}] {estado} — {titulo_crudo!r} -> {nuevo_titulo!r}")

    ruta_salida = Path(args.salida)
    ruta_salida.write_text("\n".join(salida_lineas) + "\n", encoding="utf-8")
    print(f"\nListo. Archivo generado: {ruta_salida.resolve()}")

    if no_encontrados:
        ruta_log = Path(args.log_no_encontrados)
        ruta_log.write_text("\n".join(no_encontrados) + "\n", encoding="utf-8")
        print(f"{len(no_encontrados)} títulos sin coincidencia en TMDB (se conservó su nombre original).")
        print(f"Listado guardado en: {ruta_log.resolve()}")


if __name__ == "__main__":
    main()
