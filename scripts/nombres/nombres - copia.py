import re
import time
import requests

# =====================================================================
# CONFIGURACIÓN
# =====================================================================
API_KEY = "6f6ac958e9e94c4c42371ebba58f4e00" 
BASE_URL = "https://themoviedb.org"
# Base de URL para las imágenes de TMDB (w300 es un tamaño óptimo para reproductores IPTV)
IMG_BASE_URL = "https://tmdb.org"

def limpiar_nombre_canal(texto):
    """Limpia marcas comunes de IPTV para realizar la búsqueda en TMDB."""
    texto_limpio = re.sub(r'\[.*?\]', '', texto)
    texto_limpio = re.sub(r'\(.*?\)', '', texto)
    texto_limpio = re.sub(r'\.(mp4|mkv|avi|mov)$', '', texto_limpio, flags=re.IGNORECASE)
    texto_limpio = re.sub(r'[-_|:]', ' ', texto_limpio)
    return texto_limpio.strip()

def buscar_datos_tmdb(nombre_video):
    """
    Busca en TMDB y devuelve un diccionario con:
    título en inglés, año de lanzamiento y URL del póster.
    """
    nombre_busqueda = limpiar_nombre_canal(nombre_video)
    if not nombre_busqueda:
        return None

    parametros = {
        'api_key': API_KEY,
        'query': nombre_busqueda,
        'language': 'es-MX',
        'region': 'MX'
    }

    try:
        # 1. Intentar en catálogo de Películas
        url_movie = f"{BASE_URL}/search/movie"
        response = requests.get(url_movie, params=parametros, timeout=10)
        if response.status_code == 200:
            resultados = response.json().get('results', [])
            if resultados:
                data = resultados[0]
                titulo = data.get('title')
                # Extraer solo los primeros 4 dígitos del año (YYYY-MM-DD)
                fecha = data.get('release_date', '')
                anio = fecha[:4] if fecha else ""
                # Construir la URL completa del póster
                poster_path = data.get('poster_path')
                poster_url = f"{IMG_BASE_URL}{poster_path}" if poster_path else None
                
                return {'titulo': titulo, 'anio': anio, 'poster': poster_url}

        # 2. Intentar en catálogo de Series de TV
        url_tv = f"{BASE_URL}/search/tv"
        response = requests.get(url_tv, params=parametros, timeout=10)
        if response.status_code == 200:
            resultados = response.json().get('results', [])
            if resultados:
                data = resultados[0]
                titulo = data.get('name')
                fecha = data.get('first_air_date', '')
                anio = fecha[:4] if fecha else ""
                poster_path = data.get('poster_path')
                poster_url = f"{IMG_BASE_URL}{poster_path}" if poster_path else None
                
                return {'titulo': titulo, 'anio': anio, 'poster': poster_url}

    except Exception as e:
        print(f" Error de conexión con TMDB: {e}")
    
    return None

def procesar_m3u(archivo_origen, archivo_destino):
    try:
        with open(archivo_origen, 'r', encoding='utf-8') as origen:
            lineas = origen.readlines()
        
        lineas_resultado = []
        
        if lineas and lineas[0].startswith('#EXTM3U'):
            lineas_resultado.append(lineas[0])
            inicio = 1
        else:
            inicio = 0

        print("Iniciando enriquecimiento de datos con TMDB...")
        
        for i in range(inicio, len(lineas)):
            linea = lineas[i]
            
            if linea.startswith('#EXTINF:'):
                partes = linea.split(',', 1)
                if len(partes) == 2:
                    metadatos, nombre_original = partes[0], partes[1].strip()
                    
                    print(f"Procesando: {nombre_original}...", end="", flush=True)
                    
                    info = buscar_datos_tmdb(nombre_original)
                    
                    if info:
                        # 1. Formatear el nuevo nombre con el año si está disponible
                        nuevo_nombre = info['titulo']
                        if info['anio']:
                            nuevo_nombre = f"{nuevo_nombre} ({info['anio']})"
                        
                        # 2. Inyectar el póster en las etiquetas de metadatos
                        # Si ya tiene una etiqueta tvg-logo, la reemplazamos. Si no, la creamos.
                        if info['poster']:
                            if 'tvg-logo="' in metadatos:
                                metadatos = re.sub(r'tvg-logo="[^"]*"', f'tvg-logo="{info["poster"]}"', metadatos)
                            else:
                                # Insertar justo después de '#EXTINF:-1' o los metadatos numéricos iniciales
                                metadatos = re.sub(r'(#EXTINF:[-0-9]*)', r'\1 tvg-logo="' + info['poster'] + '"', metadatos)
                        
                        # Reconstruir la línea final
                        nueva_linea = f"{metadatos},{nuevo_nombre}\n"
                        print(" -> ¡Encontrado y Actualizado!")
                    else:
                        nueva_linea = linea
                        print(" -> No encontrado en TMDB")
                        
                    lineas_resultado.append(nueva_linea)
                else:
                    lineas_resultado.append(linea)
                
                time.sleep(0.2) # Respetar límites de la API
            else:
                lineas_resultado.append(linea)

        with open(archivo_destino, 'w', encoding='utf-8') as destino:
            destino.writelines(lineas_resultado)
            
        print(f"\n¡Éxito! Nueva lista generada en '{archivo_destino}'.")

    except FileNotFoundError:
        print(f"Error: No se encontró '{archivo_origen}'.")
    except Exception as e:
        print(f"Error general en el proceso: {e}")

if __name__ == "__main__":
    if API_KEY == "TU_API_KEY_AQUI":
        print("Error: Por favor coloca tu API Key de TMDB.")
    else:
        procesar_m3u('origen.m3u', 'resultado.m3u')
