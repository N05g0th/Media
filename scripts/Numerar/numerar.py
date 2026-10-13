#!/usr/bin/env python3
"""
Renombra SOLO los archivos de video de una carpeta de forma secuencial:
    001.ext, 002.ext, 003.ext, ...
tomándolos del MÁS PESADO al MÁS LIGERO (el 001 es el archivo más grande),
y luego mueve esos archivos ya renombrados a una subcarpeta llamada
"Unix" dentro de la misma carpeta (un nivel por debajo).

Se consideran archivos de video las extensiones: mkv, mp4, avi, mov,
wmv, flv, webm, m4v, mpg, mpeg, 3gp, ts, vob. Cualquier otro archivo
(m3u, html, bat, py, imágenes, subtítulos, etc.) se ignora por completo
y no se mueve.

Además genera un archivo 0.txt con la relación entre el número asignado
y el nombre original de cada archivo (en modo simulación queda en la
carpeta original; en modo real se mueve también a "Unix"), con el
formato:

    001 nombre_original_del_archivo.ext
    002 otro_archivo.ext
    ...

También genera un archivo entrada.m3u con el formato:

    #EXTM3U
    #EXTINF:-1,nombre de la película

    #EXTINF:-1,nombre de la otra película

    ...

(se guarda y se mueve junto con 0.txt).

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
NOMBRE_M3U = "entrada.m3u"
NOMBRE_CARPETA_DESTINO = "Unix"
EXTENSIONES_VIDEO = {
    ".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm",
    ".m4v", ".mpg", ".mpeg", ".3gp", ".ts", ".vob",
}


def limpiar_nombre(nombre):
    """Quita la extensión y cualquier tag entre corchetes [ ] del nombre,
    dejando solo el nombre 'limpio' para mostrar en pantalla y en el log."""
    nombre_sin_extension = os.path.splitext(nombre)[0]
    nombre_sin_tags = re.sub(r"\[[^\]]*\]", "", nombre_sin_extension)
    # Colapsa espacios múltiples que puedan quedar tras quitar los tags.
    nombre_limpio = re.sub(r"\s+", " ", nombre_sin_tags).strip()
    return nombre_limpio


def formatear_tamano(bytes_):
    """Convierte un tamaño en bytes a un texto legible (MB, GB, ...)."""
    tamano = float(bytes_)
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if tamano < 1024 or unidad == "TB":
            return f"{tamano:.1f} {unidad}"
        tamano /= 1024


def procesar_carpeta(carpeta, simular=True):
    # Solo se toman en cuenta archivos de video; todo lo demás
    # (m3u, html, bat, py, imágenes, subtítulos, etc.) se ignora.
    candidatos = [
        f for f in os.listdir(carpeta)
        if os.path.isfile(os.path.join(carpeta, f))
        and f != NOMBRE_LOG
        and os.path.splitext(f)[1].lower() in EXTENSIONES_VIDEO
    ]

    # Orden: del más pesado al más ligero. En caso de empate de tamaño,
    # se desempata alfabéticamente para que el resultado sea estable.
    tamanos = {f: os.path.getsize(os.path.join(carpeta, f)) for f in candidatos}
    archivos = sorted(candidatos, key=lambda f: (-tamanos[f], f.lower()))

    if not archivos:
        print("No se encontraron archivos de video en la carpeta.")
        return

    cantidad_digitos = max(3, len(str(len(archivos))))

    if simular:
        print("=== MODO SIMULACIÓN (no se renombrará nada) ===\n")

    lineas_log = []
    lineas_m3u = ["#EXTM3U"]
    renombres = []  # (ruta_original, ruta_nueva, nombre_original, nuevo_nombre)

    for i, archivo in enumerate(archivos, start=1):
        extension = os.path.splitext(archivo)[1]
        numero = str(i).zfill(cantidad_digitos)
        nuevo_nombre = f"{numero}{extension}"

        ruta_original = os.path.join(carpeta, archivo)
        ruta_nueva = os.path.join(carpeta, nuevo_nombre)

        nombre_mostrado = limpiar_nombre(archivo)
        tamano_texto = formatear_tamano(tamanos[archivo])

        print(f"{numero}  {nombre_mostrado} ({tamano_texto})  →  {NOMBRE_CARPETA_DESTINO}/{nuevo_nombre}")
        lineas_log.append(f"{numero} {nombre_mostrado}")
        lineas_m3u.append(f"#EXTINF:-1,{nombre_mostrado}")
        lineas_m3u.append("")
        renombres.append((ruta_original, ruta_nueva, archivo, nuevo_nombre))

    # Escribir el log siempre, tanto en modo simulación como en modo real,
    # para que se pueda revisar el resultado antes de aplicar.
    ruta_log = os.path.join(carpeta, NOMBRE_LOG)
    with open(ruta_log, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas_log) + "\n")
    print(f"\nLista guardada en: {ruta_log}")

    ruta_m3u = os.path.join(carpeta, NOMBRE_M3U)
    with open(ruta_m3u, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas_m3u) + "\n")
    print(f"Lista M3U guardada en: {ruta_m3u}")

    if not simular:
        print("\nAplicando renombrado...\n")

        carpeta_destino = os.path.join(carpeta, NOMBRE_CARPETA_DESTINO)
        os.makedirs(carpeta_destino, exist_ok=True)

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

            # Se mueve el archivo ya renombrado a la subcarpeta destino.
            ruta_final = os.path.join(carpeta_destino, nuevo_nombre)
            if os.path.exists(ruta_final):
                print(f"  ⚠ Ya existe {nuevo_nombre} en '{NOMBRE_CARPETA_DESTINO}', se deja en la carpeta original.")
                continue
            os.rename(ruta_nueva, ruta_final)
            print(f"  ✔ {limpiar_nombre(nombre_original)} → {NOMBRE_CARPETA_DESTINO}/{nuevo_nombre}")

        # Por último, se mueve también el log (0.txt) a la subcarpeta destino.
        # os.replace sobrescribe un 0.txt previo si ya existía en 'Unix'.
        ruta_log_final = os.path.join(carpeta_destino, NOMBRE_LOG)
        os.replace(ruta_log, ruta_log_final)
        print(f"  ✔ {NOMBRE_LOG} → {NOMBRE_CARPETA_DESTINO}/{NOMBRE_LOG}")

        # Y también el archivo entrada.m3u.
        ruta_m3u_final = os.path.join(carpeta_destino, NOMBRE_M3U)
        os.replace(ruta_m3u, ruta_m3u_final)
        print(f"  ✔ {NOMBRE_M3U} → {NOMBRE_CARPETA_DESTINO}/{NOMBRE_M3U}")


def main():
    parser = argparse.ArgumentParser(
        description="Renombra videos de una carpeta de forma secuencial (del más pesado al más ligero) y genera un log en 0.txt."
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