#!/usr/bin/env python3
"""
Renombra los archivos de una carpeta de forma secuencial:
    001.ext, 002.ext, 003.ext, ...

Además genera un archivo 0.txt con la relación entre el número
asignado y el nombre original de cada archivo, con el formato:

    001 nombre_original_del_archivo.ext
    002 otro_archivo.ext
    ...

Uso:
    # Modo simulación (no renombra nada, solo muestra qué haría):
    python renombrar_secuencial.py "C:\\ruta\\a\\la\\carpeta"

    # Modo real (aplica los cambios):
    python renombrar_secuencial.py "C:\\ruta\\a\\la\\carpeta" --aplicar
"""

import os
import re
import argparse

NOMBRE_LOG = "0.txt"


def limpiar_nombre(nombre):
    """Quita la extensión y cualquier tag entre corchetes [ ] del nombre,
    dejando solo el nombre 'limpio' para mostrar en pantalla y en el log."""
    nombre_sin_extension = os.path.splitext(nombre)[0]
    nombre_sin_tags = re.sub(r"\[[^\]]*\]", "", nombre_sin_extension)
    # Colapsa espacios múltiples que puedan quedar tras quitar los tags.
    nombre_limpio = re.sub(r"\s+", " ", nombre_sin_tags).strip()
    return nombre_limpio


def procesar_carpeta(carpeta, simular=True):
    # Se ignoran carpetas y el propio archivo de log si ya existe de una corrida anterior.
    archivos = sorted(
        f for f in os.listdir(carpeta)
        if os.path.isfile(os.path.join(carpeta, f)) and f != NOMBRE_LOG
    )

    if not archivos:
        print("No se encontraron archivos en la carpeta.")
        return

    cantidad_digitos = max(3, len(str(len(archivos))))

    if simular:
        print("=== MODO SIMULACIÓN (no se renombrará nada) ===\n")

    lineas_log = []
    renombres = []  # (ruta_original, ruta_nueva, nombre_original, nuevo_nombre)

    for i, archivo in enumerate(archivos, start=1):
        extension = os.path.splitext(archivo)[1]
        numero = str(i).zfill(cantidad_digitos)
        nuevo_nombre = f"{numero}{extension}"

        ruta_original = os.path.join(carpeta, archivo)
        ruta_nueva = os.path.join(carpeta, nuevo_nombre)

        nombre_mostrado = limpiar_nombre(archivo)

        print(f"{numero}  {nombre_mostrado}  →  {nuevo_nombre}")
        lineas_log.append(f"{numero} {nombre_mostrado}")
        renombres.append((ruta_original, ruta_nueva, archivo, nuevo_nombre))

    # Escribir el log siempre, tanto en modo simulación como en modo real,
    # para que se pueda revisar el resultado antes de aplicar.
    ruta_log = os.path.join(carpeta, NOMBRE_LOG)
    with open(ruta_log, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas_log) + "\n")
    print(f"\nLista guardada en: {ruta_log}")

    if not simular:
        print("\nAplicando renombrado...\n")
        # Primero se renombra todo a un nombre temporal para evitar colisiones
        # (por ejemplo si ya existe un archivo llamado 001.ext en la carpeta).
        temporales = []
        for ruta_original, ruta_nueva, nombre_original, nuevo_nombre in renombres:
            ruta_temp = ruta_original + ".tmp_renombrar"
            os.rename(ruta_original, ruta_temp)
            temporales.append((ruta_temp, ruta_nueva, nombre_original, nuevo_nombre))

        for ruta_temp, ruta_nueva, nombre_original, nuevo_nombre in temporales:
            if os.path.exists(ruta_nueva):
                print(f"  ⚠ Ya existe {nuevo_nombre}, se omite {limpiar_nombre(nombre_original)}.")
                # Se revierte el nombre temporal a su nombre original para no perderlo.
                os.rename(ruta_temp, os.path.join(carpeta, nombre_original))
                continue
            os.rename(ruta_temp, ruta_nueva)
            print(f"  ✔ {limpiar_nombre(nombre_original)} → {nuevo_nombre}")


def main():
    parser = argparse.ArgumentParser(
        description="Renombra archivos de una carpeta de forma secuencial y genera un log en 0.txt."
    )
    parser.add_argument(
        "carpeta",
        nargs="?",
        default=None,
        help="Ruta a la carpeta con los archivos. "
             "Si no se indica, usa la misma carpeta donde está este script.",
    )
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="Aplica los cambios de verdad (sin esta bandera, solo se simula)",
    )
    args = parser.parse_args()

    carpeta = args.carpeta or os.path.dirname(os.path.abspath(__file__))

    if not os.path.isdir(carpeta):
        print("La carpeta indicada no existe.")
        return

    print(f"Carpeta a procesar: {carpeta}\n")
    procesar_carpeta(carpeta, simular=not args.aplicar)


if __name__ == "__main__":
    main()
