#!/usr/bin/env python3
"""
dedup_m3u.py

Analiza un archivo M3U (entrada.m3u), detecta enlaces (URLs) duplicados
y genera un archivo de salida (salida.m3u) donde cada enlace duplicado
aparece una sola vez, conservando todos los enlaces no duplicados.

Uso:
    python dedup_m3u.py entrada.m3u salida.m3u

Si no se pasan argumentos, usa por defecto "entrada.m3u" y "salida.m3u"
en el directorio actual.
"""

import sys


def leer_entradas(path):
    """
    Lee el archivo M3U y devuelve (cabecera, bloques).

    - cabecera: líneas previas a la primera URL (típicamente #EXTM3U).
    - bloques: lista de bloques, donde cada bloque es una lista de líneas
      (metadata como #EXTINF, #EXTVLCOPT, etc. seguida de la URL final).
    """
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lineas = [linea.rstrip("\n") for linea in f]

    cabecera = []
    bloques = []
    bloque_actual = []
    encontrada_primera_url = False

    for linea in lineas:
        contenido = linea.strip()
        if not contenido:
            continue

        if contenido.startswith("#"):
            bloque_actual.append(linea)
        else:
            bloque_actual.append(linea)
            bloques.append(bloque_actual)
            bloque_actual = []
            encontrada_primera_url = True

    # Si la primera línea es #EXTM3U, la sacamos del primer bloque
    # y la ponemos como cabecera del archivo.
    if bloques and bloques[0][0].strip().upper().startswith("#EXTM3U"):
        cabecera.append(bloques[0][0])
        bloques[0] = bloques[0][1:]
        if not bloques[0]:
            bloques.pop(0)

    # Si quedaron líneas sueltas sin URL al final, se ignoran (incompletas)
    return cabecera, bloques


def obtener_url(bloque):
    """La URL de un bloque es su última línea (la que no empieza con #)."""
    return bloque[-1].strip()


def deduplicar(cabecera, bloques):
    vistos = set()
    resultado = []
    duplicados = 0

    for bloque in bloques:
        url = obtener_url(bloque)
        if url in vistos:
            duplicados += 1
            continue
        vistos.add(url)
        resultado.append(bloque)

    return resultado, duplicados


def escribir_salida(path, cabecera, bloques):
    with open(path, "w", encoding="utf-8") as f:
        for linea in cabecera:
            f.write(linea + "\n")
        for bloque in bloques:
            for linea in bloque:
                f.write(linea + "\n")


def main():
    entrada = sys.argv[1] if len(sys.argv) > 1 else "entrada.m3u"
    salida = sys.argv[2] if len(sys.argv) > 2 else "salida.m3u"

    cabecera, bloques = leer_entradas(entrada)
    total_original = len(bloques)

    bloques_unicos, duplicados = deduplicar(cabecera, bloques)

    escribir_salida(salida, cabecera, bloques_unicos)

    print(f"Enlaces totales encontrados : {total_original}")
    print(f"Enlaces duplicados eliminados: {duplicados}")
    print(f"Enlaces únicos en la salida  : {len(bloques_unicos)}")
    print(f"Archivo generado: {salida}")


if __name__ == "__main__":
    main()
