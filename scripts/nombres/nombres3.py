import re
import time
import requests

# =====================================================================
# CONFIGURACIÓN
# =====================================================================
API_KEY = "6f6ac958e9e94c4c42371ebba58f4e00" 
BASE_URL = "https://themoviedb.org"

def limpiar_nombre_canal(texto):
    """
    Limpia a fondo el nombre eliminando corchetes, paréntesis y años
    para dejar solo el título puro que TMDB sí puede indexar.
    """
    texto_limpio = re.sub(r'\[.*?\]', '', texto)  # Elimina [ENG], [HD], etc.
    texto_limpio = re.sub(r'\(.*?\)', '', texto)  # Elimina (2025), (1080p), etc.
    texto_limpio = re.sub(r'\.(mp4|mkv|avi|mov)$', '', texto_limpio, flags=re.IGNORECASE)
    texto_limpio = re.sub(r'[-_|:]', ' ', texto_limpio)
    return texto_limpio.strip()

def hacer_peticion(url, parametros):
    """Maneja las peticiones de forma segura emulando un navegador."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    parametros['api_key'] = API_KEY

    try:
        response = requests.get(url, params=parametros, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None

def buscar_datos_tmdb(nombre_video):
    nombre_busqueda = limpiar_nombre_canal(nombre_video)
    if not nombre_busqueda:
        return None

    # Parámetros óptimos para Español de México
    parametros = {
        'query': nombre_busqueda,
        'language': 'es-MX',
        'region': 'MX'
    }

    # 1. Buscar en Películas
    data_movie = hacer_peticion(f"{BASE_URL}/search/movie", parametros)
    if data_movie and data_movie.get('results'):
        # CORRECCIÓN: Extraemos el primer elemento [0] de la lista de resultados
        primer_resultado = data_movie['results'][0]
        titulo = primer_resultado.get('title')
        fecha = primer_resultado.get('release_date', '')
        anio = fecha[:4] if fecha else ""
        return {'titulo': titulo, 'anio': anio}

    # 2. Buscar en Series de TV
    data_tv = hacer_peticion(f"{BASE_URL}/search/tv", parametros)
    if data_tv and data_tv.get('results'):
        # CORRECCIÓN: Extraemos el primer elemento [0] de la lista de resultados
        primer_resultado = data_tv['results'][0]
        titulo = primer_resultado.get('name')
        fecha = primer_resultado.get('first_air_date', '')
        anio = fecha[:4] if fecha else ""
        return {'titulo': titulo, 'anio': anio}

    return None

def procesar_m3u(archivo_origen, archivo_resultado, archivo_encontrados):
    try:
        with open(archivo_origen, 'r', encoding='utf-8') as origen:
            lineas = origen.readlines()
        
        lineas_resultado = []
        lineas_encontrados = []
        
        # CORRECCIÓN: Analizar la primera línea [0] de la lista como string
        inicio = 1 if lineas and lineas[0].startswith('#EXTM3U') else 0
        if inicio == 1:
            lineas_resultado.append(lineas[0])
            lineas_encontrados.append(lineas[0])

        print("Iniciando búsqueda de títulos en TMDB (Español de México)...\n")
        
        for i in range(inicio, len(lineas)):
            linea = lineas[i]
            
            if linea.startswith('#EXTINF:'):
                partes = linea.split(',', 1)
                if len(partes) == 2:
                    metadatos, nombre_original = partes[0], partes[1].strip()
                    
                    print(f"Procesando: {nombre_original:<50}", end="", flush=True)
                    
                    info = buscar_datos_tmdb(nombre_original)
                    
                    tiene_url = (i + 1 < len(lineas))
                    linea_url = lineas[i + 1] if tiene_url else ""
                    
                    if info:
                        nuevo_nombre = info['titulo']
                        if info['anio']:
                            nuevo_nombre = f"{nuevo_nombre} ({info['anio']})"
                        
                        nueva_linea_inf = f"{metadatos},{nuevo_nombre}\n"
                        print(f" -> ¡Traducido!: {nuevo_nombre}")
                        
                        lineas_resultado.append(nueva_linea_inf)
                        if tiene_url:
                            lineas_resultado.append(linea_url)
                            
                        lineas_encontrados.append(nueva_linea_inf)
                        if tiene_url:
                            lineas_encontrados.append(linea_url)
                    else:
                        print(" -> No encontrado")
                        lineas_resultado.append(linea)
                        if tiene_url:
                            lineas_resultado.append(linea_url)
                else:
                    lineas_resultado.append(linea)
                
                time.sleep(0.25)
            
            elif i > 0 and lineas[i-1].startswith('#EXTINF:'):
                continue
            else:
                if i != 0: 
                    lineas_resultado.append(linea)

        with open(archivo_resultado, 'w', encoding='utf-8') as dest_res:
            dest_res.writelines(lineas_resultado)
            
        with open(archivo_encontrados, 'w', encoding='utf-8') as dest_enc:
            dest_enc.writelines(lineas_encontrados)
            
        print(f"\n¡Proceso terminado con éxito!")
        print(f"-> Lista General con cambios: '{archivo_resultado}'")
        print(f"-> Lista de Solo Encontrados: '{archivo_encontrados}'")

    except FileNotFoundError:
        print(f"Error: No se encontró el archivo '{archivo_origen}' en esta carpeta.")
    except Exception as e:
        print(f"Error general en el proceso: {e}")

if __name__ == "__main__":
    procesar_m3u('origen.m3u', 'resultado.m3u', 'encontrados.m3u')
