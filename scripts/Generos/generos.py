#!/usr/bin/env python3
"""
Script para organizar una lista M3U por género y agregar el póster de
cada película, usando la API de TMDB.

Lee 'entrada.m3u', busca cada título en The Movie Database (TMDB),
obtiene su género principal y la URL de su póster, y genera 'salida.m3u'
con los tags group-title="<Género>" y tvg-logo="<URL del póster>" en
cada entrada.

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
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"  # tamaño del póster

# Géneros que NO se deben usar como group-title, aunque la película los tenga
GENEROS_EXCLUIDOS = {"Bélica", "Familia", "Misterio", "Música", "Historia", "Crimen"}


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


def buscar_pelicula(titulo, mapa_generos):
    """Busca la película en TMDB y devuelve (genero_principal, poster_url)."""
    try:
        resp = requests.get(
            TMDB_SEARCH_URL,
            params={"api_key": API_KEY, "query": titulo, "language": IDIOMA},
            timeout=10,
        )
        resp.raise_for_status()
        resultados = resp.json().get("results", [])
        if not resultados:
            return "Sin clasificar", None

        pelicula = resultados[0]

        ids_genero = pelicula.get("genre_ids", [])
        nombres_genero = [mapa_generos.get(gid, "Desconocido") for gid in ids_genero]
        nombres_validos = [n for n in nombres_genero if n not in GENEROS_EXCLUIDOS]

        if not nombres_genero:
            genero = "Sin género"
        elif nombres_validos:
            genero = nombres_validos[0]
        else:
            # Todos los géneros de la película están en la lista de excluidos
            genero = "Sin género"

        poster_path = pelicula.get("poster_path")
        poster_url = f"{TMDB_IMAGE_BASE_URL}{poster_path}" if poster_path else None

        return genero, poster_url
    except requests.RequestException as e:
        print(f"  ! Error buscando '{titulo}': {e}")
        return "Error de búsqueda", None


def _insertar_atributo(info_original, nombre_atributo, valor):
    """Inserta o reemplaza un atributo (ej. group-title, tvg-logo) en la línea EXTINF."""
    if not valor:
        return info_original  # deja la línea sin cambios si no hay valor

    patron = rf'{nombre_atributo}="[^"]*"'
    if re.search(patron, info_original):
        return re.sub(patron, f'{nombre_atributo}="{valor}"', info_original)

    partes = info_original.split(",", 1)
    if len(partes) == 2:
        return f'{partes[0]} {nombre_atributo}="{valor}",{partes[1]}'
    return info_original  # fallback por si el formato es inesperado


def construir_extinf(info_original, genero, poster_url):
    """Inserta o reemplaza los atributos group-title y tvg-logo en la línea EXTINF."""
    info = _insertar_atributo(info_original, "group-title", genero)
    info = _insertar_atributo(info, "tvg-logo", poster_url)
    return info


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

        genero, poster_url = buscar_pelicula(titulo_limpio, mapa_generos)
        print(f"    -> Género: {genero}")
        print(f"    -> Póster: {poster_url if poster_url else 'No encontrado'}")

        nueva_info = construir_extinf(entrada["info"], genero, poster_url)
        lineas_salida.append(nueva_info)
        lineas_salida.append(entrada["url"])

        time.sleep(PAUSA_ENTRE_PETICIONES)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas_salida) + "\n")

    print(f"\nListo. Archivo generado: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()