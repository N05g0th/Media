import re
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom

# Configuración
M3U_URL = "https://raw.githubusercontent.com/N05g0th/Media/refs/heads/main/Peliculas.m3u"
OUTPUT_FILE = "peliculas_dummy.xml"

def descargar_y_parsear_m3u(url):
    print("Descargando archivo M3U...")
    respuesta = requests.get(url)
    respuesta.raise_for_status()
    lineas = respuesta.text.splitlines()
    
    peliculas = []
    # Regex para extraer el tvg-id o el nombre de la línea #EXTINF
    # Si no tiene tvg-id, usará el nombre de la película como ID único
    for i, linea in enumerate(lineas):
        if linea.startswith("#EXTINF"):
            tvg_id_match = re.search(r'tvg-id="([^"]+)"', linea)
            
            # El nombre de la película suele estar después de la última coma
            partes_linea = linea.split(",")
            nombre_pelicula = partes_linea[-1].strip() if partes_linea else "Película Desconocida"
            
            # Si tiene tvg-id lo usa, si no, limpia el nombre para usarlo como id
            if tvg_id_match:
                canal_id = tvg_id_match.group(1)
            else:
                canal_id = re.sub(r'[^a-zA-Z0-9]', '', nombre_pelicula)
            
            peliculas.append({
                "id": canal_id,
                "nombre": nombre_pelicula
            })
    return peliculas

def generar_xmltv(peliculas, archivo_salida):
    print(f"Generando XMLTV para {len(peliculas)} películas...")
    
    # Nodo raíz <tv>
    root = ET.Element("tv", {
        "generator-info-name": "Python M3U to XMLTV Generator",
        "generator-info-url": "http://localhost"
    })
    
    # 1. Crear los elementos <channel>
    for pelicula in peliculas:
        channel = ET.SubElement(root, "channel", {"id": pelicula["id"]})
        display_name = ET.SubElement(channel, "display-name")
        display_name.text = pelicula["nombre"]
        
    # 2. Crear la programación continua (24/7) para cada elemento <programme>
    # Cubre un amplio rango de fechas para evitar mantenimiento diario
    for pelicula in peliculas:
        programme = ET.SubElement(root, "programme", {
            "start": "20260101000000 +0000",
            "stop": "20301231235959 +0000",
            "channel": pelicula["id"]
        })
        
        title = ET.SubElement(programme, "title", {"lang": "es"})
        title.text = pelicula["nombre"]
        
        desc = ET.SubElement(programme, "desc", {"lang": "es"})
        desc.text = f"Contenido multimedia bajo demanda (VOD): '{pelicula['nombre']}'. Disponible para reproducir en cualquier momento (24/7)."
        
        category = ET.SubElement(programme, "category", {"lang": "es"})
        category.text = "Películas"

    # Formatear el XML para que sea legible (con sangrías)
    xml_str = ET.tstring(root, encoding="utf-8")
    reparsed = minidom.parseString(xml_str)
    xml_formateado = reparsed.toprettyxml(indent="  ")
    
    # Añadir la declaración de tipo de documento (DTD) requerida por XMLTV
    lineas_xml = xml_formateado.splitlines()
    if lineas_xml and lineas_xml[0].startswith("<?xml"):
        lineas_xml.insert(1, '<!DOCTYPE tv SYSTEM "xmltv.dtd">')
    
    with open(archivo_salida, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas_xml))
        
    print(f"¡Archivo generado con éxito!: {archivo_salida}")

if __name__ == "__main__":
    try:
        lista_peliculas = descargar_y_parsear_m3u(M3U_URL)
        if lista_peliculas:
            generar_xmltv(lista_peliculas, OUTPUT_FILE)
        else:
            print("No se encontraron elementos válidos en el archivo M3U.")
    except Exception as e:
        print(f"Ocurrió un error: {e}")
