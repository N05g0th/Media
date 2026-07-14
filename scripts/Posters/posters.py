#!/usr/bin/env python3
"""
Script para agregar el póster de cada película (tvg-logo) usando TMDB.

Lee 'entrada.m3u', busca cada título en The Movie Database (TMDB),
obtiene la URL de su póster y genera 'salida.m3u' con el tag
tvg-logo="<URL del póster>" en cada entrada.

Requisitos:
    pip install requests

Uso:
    python organizar_m3u_por_genero.py
    (asegúrate de tener entrada.m3u en el mismo directorio)
"""

import re
import time
import requests

# ----------------------------------------------------------------------
# Configuración
# ----------------------------------------------------------------------
API_KEY = "6f6ac958e9e94c4c42371ebba58f4e00"
INPUT_FILE = "entrada.m3u"
OUTPUT_FILE = "salida.m3u"
IDIOMA = "es-MX"          # idioma para los resultados de búsqueda
PAUSA_ENTRE_PETICIONES = 0.25  # segundos, para no saturar la API

TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"  # tamaño del póster


# ----------------------------------------------------------------------
# Funciones
# ----------------------------------------------------------------------
def parsear_m3u(ruta):
    """Extrae las entradas (EXTINF + URL) de un archivo M3U."""
    with open(ruta, "r", encoding="utf-8") as f:
        lineas = [l.rstrip("\n") for l in f]

    entradas = []
    i = 0
    while i < len(lineas):
        linea = lineas[i]
        if linea.startswith("#EXTINF"):
            titulo = linea.split(",", 1)[-1].strip()
            url = lineas[i + 1] if i + 1 < len(lineas) else ""
            entradas.append({"info": linea, "titulo": titulo, "url": url})
            i += 2
        else:
            i += 1
    return entradas


def limpiar_titulo(titulo_original):
    """Quita año entre paréntesis, corchetes de calidad, etc, para mejorar la búsqueda."""
    titulo = re.sub(r"\(\d{4}\)", "", titulo_original)
    titulo = re.sub(r"\[.*?\]", "", titulo)
    titulo = re.sub(r"\s{2,}", " ", titulo)
    return titulo.strip()


def buscar_poster(titulo):
    """Busca la película en TMDB y devuelve la URL completa de su póster."""
    try:
        resp = requests.get(
            TMDB_SEARCH_URL,
            params={"api_key": API_KEY, "query": titulo, "language": IDIOMA},
            timeout=10,
        )
        resp.raise_for_status()
        resultados = resp.json().get("results", [])
        if not resultados:
            return None

        poster_path = resultados[0].get("poster_path")
        if not poster_path:
            return None

        return f"{TMDB_IMAGE_BASE_URL}{poster_path}"
    except requests.RequestException as e:
        print(f"  ! Error buscando '{titulo}': {e}")
        return None


def construir_extinf(info_original, poster_url):
    """Inserta o reemplaza el atributo tvg-logo en la línea EXTINF."""
    if not poster_url:
        return info_original  # deja la línea sin cambios si no se encontró póster

    if 'tvg-logo="' in info_original:
        return re.sub(r'tvg-logo="[^"]*"', f'tvg-logo="{poster_url}"', info_original)

    # Inserta tvg-logo justo después de #EXTINF:-1 (o duración) y antes del resto de atributos
    match = re.match(r"(#EXTINF:[^\s]*)(.*)", info_original)
    if match:
        return f'{match.group(1)} tvg-logo="{poster_url}"{match.group(2)}'
    return info_original  # fallback por si el formato es inesperado


# ----------------------------------------------------------------------
# Programa principal
# ----------------------------------------------------------------------
def main():
    print(f"Leyendo {INPUT_FILE}...")
    entradas = parsear_m3u(INPUT_FILE)
    print(f"{len(entradas)} entradas encontradas.\n")

    lineas_salida = ["#EXTM3U"]

    for idx, entrada in enumerate(entradas, start=1):
        titulo_limpio = limpiar_titulo(entrada["titulo"])
        print(f"[{idx}/{len(entradas)}] Buscando: {titulo_limpio}")

        poster_url = buscar_poster(titulo_limpio)
        print(f"    -> Póster: {poster_url if poster_url else 'No encontrado'}")

        nueva_info = construir_extinf(entrada["info"], poster_url)
        lineas_salida.append(nueva_info)
        lineas_salida.append(entrada["url"])

        time.sleep(PAUSA_ENTRE_PETICIONES)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas_salida) + "\n")

    print(f"\nListo. Archivo generado: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
