import re

def encontrar_duplicados(archivo_entrada, archivo_salida):
    vistos = set()
    duplicados = set()
    
    with open(archivo_entrada, 'r', encoding='utf-8') as f:
        lineas = f.readlines()
        
    for linea in lineas:
        linea_limpia = linea.strip()
        if not linea_limpia:
            continue
            
        # Elimina lo que está dentro de [] y espacios extra
        titulo_normalizado = re.sub(r'\[.*?\]', '', linea_limpia).strip().lower()
        
        if titulo_normalizado in vistos:
            duplicados.add(linea_limpia)
        else:
            vistos.add(titulo_normalizado)
            
    with open(archivo_salida, 'w', encoding='utf-8') as f:
        for peli in sorted(duplicados):
            f.write(peli + '\n')

encontrar_duplicados('listado.txt', 'duplicados.txt')
