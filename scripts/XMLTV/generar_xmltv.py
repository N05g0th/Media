import re
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom

# Tu enlace directo de GitHub
M3U_URL = "https://raw.githubusercontent.com/N05g0th/Media/refs/heads/main/Peliculas.m3u"
OUTPUT_FILE = "peliculas_dummy.xml"

def procesar_m3u_remoto(url):
    print(f"Conectando al repositorio de GitHub para leer las películas...")
    cabeceras = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/plain,text/html'
    }
    
    # Descarga directa con tiempo de espera extendido
    respuesta = requests.get(url, headers=cabeceras, timeout=30)
    respuesta.raise_for_status()
    lineas = respuesta.text.splitlines()
    
    peliculas = []
    for linea in lineas:
        if linea.startswith("#EXTINF"):
            # Buscar el identificador tvg-id en tu lista
            tvg_id_match = re.search(r'tvg-id="([^"]+)"', linea)
            
            # Extraer el nombre de la película después de la última coma
            partes = linea.split(",")
            nombre = partes[-1].strip() if partes else "Película"
            
            # Si tu M3U no define un tvg-id, creamos uno limpio con el nombre
            if tvg_id_match:
                canal_id = tvg_id_match.group(1)
            else:
                canal_id = re.sub(r'[^a-zA-Z0-9]', '', nombre)
            
            peliculas.append({
                "id": canal_id,
                "nombre": nombre
            })
    return peliculas

def crear_archivo_xmltv(lista_peliculas, ruta_salida):
    print(f"Escribiendo XMLTV para {len(lista_peliculas)} títulos detectados...")
    
    # Estructura del nodo raíz <tv>
    root = ET.Element("tv", {
        "generator-info-name": "N05g0th Media XMLTV Generator",
        "generator-info-url": "https://github.com"
    })
    
    # Bloque de canales
    for peli in lista_peliculas:
        channel = ET.SubElement(root, "channel", {"id": peli["id"]})
        display_name = ET.SubElement(channel, "display-name")
        display_name.text = peli["nombre"]
        
    # Bloque de programación perpetua (24/7 de 2026 a 2030)
    for peli in lista_peliculas:
        programme = ET.SubElement(root, "programme", {
            "start": "20260101000000 +0000",
            "stop": "20301231235959 +0000",
            "channel": peli["id"]
        })
        
        title = ET.SubElement(programme, "title", {"lang": "es"})
        title.text = peli["nombre"]
        
        desc = ET.SubElement(programme, "desc", {"lang": "es"})
        desc.text = f"Película en formato VoD (Bajo Demanda): '{peli['nombre']}'. Disponible de forma inmediata para reproducción continua 24/7."
        
        category = ET.SubElement(programme, "category", {"lang": "es"})
        category.text = "Películas"

    # Formatear el árbol XML
    xml_puro = ET.tostring(root, encoding="utf-8")
    dom_reparsed = minidom.parseString(xml_puro)
    xml_formateado = dom_reparsed.toprettyxml(indent="  ")
    
    # Insertar el DTD oficial de XMLTV
    lineas_finales = xml_formateado.splitlines()
    lineas_finales.insert(1, '<!DOCTYPE tv SYSTEM "xmltv.dtd">')
    
    with open(ruta_salida, "w", encoding="utf-8") as archivo:
        archivo.write("\n".join(lineas_finales))
        
    print(f"¡Guía generada con éxito!: {ruta_salida}")

if __name__ == "__main__":
    try:
        peliculas = procesar_m3u_remoto(M3U_URL)
        if peliculas:
            crear_archivo_xmltv(peliculas, OUTPUT_FILE)
        else:
            print("❌ El archivo M3U se leyó pero está vacío o no contiene líneas #EXTINF.")
    except Exception as error:
        print(f"\n❌ Error de ejecución: {error}")
