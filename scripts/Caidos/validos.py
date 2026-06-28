import asyncio
import aiohttp
import re

# Configuración de archivos
ARCHIVO_ENTRADA = "lista.m3u"
ARCHIVO_VALIDOS = "validos.m3u"
ARCHIVO_CAIDOS = "caidos.m3u"

# Límite de conexiones simultáneas para no saturar tu red o el servidor
SEMÁFORO = asyncio.Semaphore(10) 
TIMEOUT = aiohttp.ClientTimeout(total=5)

async def validar_enlace(session, nombre, url):
    """Verifica si un enlace responde con un estado HTTP exitoso."""
    async with SEMÁFORO:
        try:
            async with session.head(url, timeout=TIMEOUT, allow_redirects=True) as response:
                if response.status in [200, 201, 206]:
                    return True, nombre, url
        except:
            pass
        
        # Intento secundario con GET si HEAD falla (algunos servidores bloquean HEAD)
        try:
            async with session.get(url, timeout=TIMEOUT, allow_redirects=True) as response:
                if response.status in [200, 201, 206]:
                    return True, nombre, url
        except:
            pass
            
        return False, nombre, url

def limpiar_nombre_canal(linea_extinf):
    """Extrae únicamente el nombre limpio del canal omitiendo los metadatos del #EXTINF."""
    if "," in linea_extinf:
        # El nombre del canal siempre va después de la última coma en la línea #EXTINF
        return linea_extinf.split(",")[-1].strip()
    return linea_extinf

def leer_m3u(ruta):
    """Lee el archivo M3U y extrae los canales con sus URLs."""
    canales = []
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            lineas = f.readlines()
            
        nombre_actual = ""
        for linea in lineas:
            linea = linea.strip()
            if linea.startswith("#EXTM3U"):
                continue
            elif linea.startswith("#EXTINF"):
                nombre_actual = linea
            elif linea.startswith("http") or linea.startswith("https"):
                if nombre_actual:
                    canales.append((nombre_actual, linea))
                else:
                    canales.append(("#EXTINF:-1,Canal sin nombre", linea))
                    nombre_actual = ""
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo '{ruta}'")
    return canales

async def main():
    canales = leer_m3u(ARCHIVO_ENTRADA)
    if not canales:
        print("No se encontraron canales para procesar.")
        return

    total_canales = len(canales)
    print(f"Procesando {total_canales} enlaces...\n")
    
    validos_count = 0
    caidos_count = 0

    # Abrimos los archivos de salida para escritura en tiempo real
    with open(ARCHIVO_VALIDOS, "w", encoding="utf-8") as f_val, \
         open(ARCHIVO_CAIDOS, "w", encoding="utf-8") as f_cai:
        
        f_val.write("#EXTM3U\n")
        f_cai.write("#EXTM3U\n")
        
        async with aiohttp.ClientSession() as session:
            tareas = [validar_enlace(session, nombre, url) for nombre, url in canales]
            
            for tarea_terminada in asyncio.as_completed(tareas):
                es_valido, nombre, url = await tarea_terminada
                
                if es_valido:
                    f_val.write(f"{nombre}\n{url}\n")
                    validos_count += 1
                else:
                    f_cai.write(f"{nombre}\n{url}\n")
                    caidos_count += 1
                    
                    # Limpiamos el nombre para que la consola se vea ordenada
                    nombre_limpio = limpiar_nombre_canal(nombre)
                    
                    # Mostramos el reporte incluyendo el nombre del canal que falló
                    print(f"[CAÍDO] {nombre_limpio:<30} | Válidos: {validos_count} | Caídos: {caidos_count} | Restantes: {total_canales - (validos_count + caidos_count)}")

    print("\n" + "="*50)
    print("Proceso finalizado con éxito.")
    print(f"Enlaces válidos guardados: {validos_count} -> {ARCHIVO_VALIDOS}")
    print(f"Enlaces caídos guardados: {caidos_count} -> {ARCHIVO_CAIDOS}")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())