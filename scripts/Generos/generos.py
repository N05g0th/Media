#!/usr/bin/env python3
"""
Script para organizar una lista M3U por género usando la API de TMDB.

Lee 'entrada.m3u', busca cada título en The Movie Database (TMDB),
obtiene su género principal y genera 'salida.m3u' con el tag
group-title="<Género>" en cada entrada.

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
IDIOMA = "es-MX"          # idioma para nombres de género y resultados
PAUSA_ENTRE_PETICIONES = 0.25  # segundos, para no saturar la API

TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_GENRE_URL = "https://api.themoviedb.org/3/genre/movie/list"


# ----------------------------------------------------------------------
# Funciones
# ----------------------------------------------------------------------
def obtener_generos():
    """Descarga el catálogo de géneros de TMDB (id -> nombre)."""
    resp = requests.get(
        TMDB_GENRE_URL,
        params={"api_key": API_KEY, "language": IDIOMA},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return {g["id"]: g["name"] for g in data["genres"]}


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


def buscar_genero(titulo, mapa_generos):
    """Busca la película en TMDB y devuelve el nombre de su género principal."""
    try:
        resp = requests.get(
            TMDB_SEARCH_URL,
            params={"api_key": API_KEY, "query": titulo, "language": IDIOMA},
            timeout=10,
        )
        resp.raise_for_status()
        resultados = resp.json().get("results", [])
        if not resultados:
            return "Sin clasificar"

        pelicula = resultados[0]
        ids_genero = pelicula.get("genre_ids", [])
        if not ids_genero:
            return "Sin género"

        return mapa_generos.get(ids_genero[0], "Desconocido")
    except requests.RequestException as e:
        print(f"  ! Error buscando '{titulo}': {e}")
        return "Error de búsqueda"


def construir_extinf(info_original, genero):
    """Inserta o reemplaza el atributo group-title en la línea EXTINF."""
    if 'group-title="' in info_original:
        return re.sub(r'group-title="[^"]*"', f'group-title="{genero}"', info_original)

    partes = info_original.split(",", 1)
    if len(partes) == 2:
        return f'{partes[0]} group-title="{genero}",{partes[1]}'
    return info_original  # fallback por si el formato es inesperado


# ----------------------------------------------------------------------
# Programa principal
# ----------------------------------------------------------------------
def main():
    print("Obteniendo catálogo de géneros de TMDB...")
    mapa_generos = obtener_generos()

    print(f"Leyendo {INPUT_FILE}...")
    entradas = parsear_m3u(INPUT_FILE)
    print(f"{len(entradas)} entradas encontradas.\n")

    lineas_salida = ["#EXTM3U"]

    for idx, entrada in enumerate(entradas, start=1):
        titulo_limpio = limpiar_titulo(entrada["titulo"])
        print(f"[{idx}/{len(entradas)}] Buscando: {titulo_limpio}")

        genero = buscar_genero(titulo_limpio, mapa_generos)
        print(f"    -> Género: {genero}")

        nueva_info = construir_extinf(entrada["info"], genero)
        lineas_salida.append(nueva_info)
        lineas_salida.append(entrada["url"])

        time.sleep(PAUSA_ENTRE_PETICIONES)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas_salida) + "\n")

    print(f"\nListo. Archivo generado: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()