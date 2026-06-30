def filtrar_m3u(archivo_origen, archivo_con, archivo_sin):
    try:
        with open(archivo_origen, 'r', encoding='utf-8') as origen:
            lineas = origen.readlines()
        
        lista_con = []
        lista_sin = []
        
        # Manejo de la cabecera estándar de IPTV
        cabecera = "#EXTM3U\n"
        if lineas and lineas[0].startswith('#EXTM3U'):
            cabecera = lineas[0]
            inicio = 1
        else:
            inicio = 0

        lista_con.append(cabecera)
        lista_sin.append(cabecera)

        # Recorremos el archivo analizando los bloques de canales
        for i in range(inicio, len(lineas)):
            linea = lineas[i].strip()
            
            # Buscamos la línea de metadatos (información del canal)
            if linea.startswith('#EXTINF:'):
                # Verificamos si la línea siguiente (URL) existe para no romper el script
                tiene_url = (i + 1 < len(lineas))
                
                # Condición: Contiene corchetes [ ]
                if '[' in linea and ']' in linea:
                    lista_con.append(lineas[i])
                    if tiene_url:
                        lista_con.append(lineas[i + 1])
                # Condición: NO contiene corchetes [ ]
                else:
                    lista_sin.append(lineas[i])
                    if tiene_url:
                        lista_sin.append(lineas[i + 1])

        # Guardamos la lista CON corchetes
        with open(archivo_con, 'w', encoding='utf-8') as dest_con:
            dest_con.writelines(lista_con)
            
        # Guardamos la lista SIN corchetes
        with open(archivo_sin, 'w', encoding='utf-8') as dest_sin:
            dest_sin.writelines(lista_sin)
            
        print("¡Proceso completado con éxito!")
        print(f"-> Canales con [ ]: '{archivo_con}'")
        print(f"-> Canales sin [ ]: '{archivo_sin}'")

    except FileNotFoundError:
        print(f"Error: No se encontró el archivo '{archivo_origen}'.")
    except Exception as e:
        print(f"Ocurrió un error inesperado: {e}")

# Ejecutar el script con los tres nombres de archivo
filtrar_m3u('lista.m3u', 'resultado.m3u', 'sin.m3u')
