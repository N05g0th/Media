import os

CARPETAS_EXCLUIDAS = {"$RECYCLE.BIN"}


def listar_estructura(ruta_inicial="."):
    """
    Recorre la ruta indicada (por defecto, el directorio donde se ejecuta
    el script) e imprime todas las carpetas, subcarpetas y archivos
    que encuentre, mostrando la jerarquía con sangría.
    """
    ruta_inicial = os.path.abspath(ruta_inicial)
    print(f"Estructura de: {ruta_inicial}\n")

    for raiz, carpetas, archivos in os.walk(ruta_inicial):
        # Excluir carpetas no deseadas para que os.walk no entre en ellas
        carpetas[:] = [c for c in carpetas if c not in CARPETAS_EXCLUIDAS]

        # Nivel de profundidad respecto a la ruta inicial (para la sangría)
        nivel = raiz.replace(ruta_inicial, "").count(os.sep)
        sangria = "    " * nivel
        nombre_carpeta = os.path.basename(raiz) or raiz
        print(f"{sangria}📁 {nombre_carpeta}/")

        sangria_archivo = "    " * (nivel + 1)
        for archivo in sorted(archivos):
            print(f"{sangria_archivo}📄 {archivo}")


def guardar_estructura_en_txt(ruta_inicial=".", nombre_salida="estructura.txt"):
    """
    Igual que listar_estructura, pero guarda el resultado en un archivo
    de texto en lugar de (o además de) imprimirlo en consola.
    El archivo se guarda siempre en la misma carpeta donde está este script,
    sin importar cuál sea la ruta analizada.
    """
    ruta_inicial = os.path.abspath(ruta_inicial)
    carpeta_del_script = os.path.dirname(os.path.abspath(__file__))
    ruta_salida = os.path.join(carpeta_del_script, nombre_salida)

    with open(ruta_salida, "w", encoding="utf-8") as f:
        f.write(f"Estructura de: {ruta_inicial}\n\n")
        for raiz, carpetas, archivos in os.walk(ruta_inicial):
            carpetas[:] = [c for c in carpetas if c not in CARPETAS_EXCLUIDAS]

            nivel = raiz.replace(ruta_inicial, "").count(os.sep)
            sangria = "    " * nivel
            nombre_carpeta = os.path.basename(raiz) or raiz
            f.write(f"{sangria}📁 {nombre_carpeta}/\n")

            sangria_archivo = "    " * (nivel + 1)
            for archivo in sorted(archivos):
                f.write(f"{sangria_archivo}📄 {archivo}\n")
    print(f"Estructura guardada en: {ruta_salida}")


if __name__ == "__main__":
    ruta_a_analizar = input("Ingresa el path a analizar (Enter para usar la carpeta actual): ").strip()
    if not ruta_a_analizar:
        ruta_a_analizar = "."

    listar_estructura(ruta_a_analizar)
    guardar_estructura_en_txt(ruta_a_analizar, nombre_salida="enlistado.txt")