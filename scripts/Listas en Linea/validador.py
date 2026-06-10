import os
import requests

def verificar_lista_profunda():
    os.makedirs("online", exist_ok=True)
    os.makedirs("caidos", exist_ok=True)
    
    archivos = [f for f in os.listdir('.') if f.endswith('.m3u') or f.endswith('.m3u8')]
    
    for archivo in archivos:
        links = []
        with open(archivo, 'r', encoding='utf-8', errors='ignore') as f:
            for linea in f:
                linea = linea.strip()
                if linea.startswith("http://") or linea.startswith("https://"):
                    links.append(linea)
        
        if not links:
            os.rename(archivo, os.path.join("caidos", archivo))
            continue
            
        # Probar hasta 5 enlaces para sacar un promedio
        enlaces_a_probar = links[:5]
        funcionando = 0
        
        for link in enlaces_a_probar:
            try:
                respuesta = requests.head(link, timeout=4, allow_redirects=True)
                if respuesta.status_code in [200, 206, 302]:
                    funcionando += 1
            except requests.RequestException:
                continue
        
        # Si al menos un canal funciona, se guarda en online
        if funcionando > 0:
            os.rename(archivo, os.path.join("online", archivo))
        else:
            os.rename(archivo, os.path.join("caidos", archivo))

if __name__ == "__main__":
    verificar_lista_profunda()
