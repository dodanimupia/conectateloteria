"""
Lógica de scraping: obtiene los resultados de lotería y los guarda en
datos_loteria.json. Este script lo ejecuta GitHub Actions cada 5 minutos
(ver .github/workflows/actualizar.yml), pero también puedes correrlo a
mano en tu computadora.

Requiere: pip install playwright beautifulsoup4  /  playwright install chromium
"""

import json
import datetime
from bs4 import BeautifulSoup

URL = "https://loterias.conectate.com.do/"
SNAPSHOT_LOCAL = "leidsa_snapshot.html"
ARCHIVO_DATOS = "datos_loteria.json"

# Primer segmento de la URL de cada juego -> nombre de la empresa/lotería
EMPRESAS = {
    "nacional": "Lotería Nacional",
    "leidsa": "Leidsa",
    "loto-real": "Lotería Real",
    "loteka": "Loteka",
    "americanas": "Americanas (NY)",
    "la-primera": "La Primera",
    "la-suerte-dominicana": "La Suerte",
    "lotedom": "LoteDom",
    "anguilla": "Anguila",
    "king-lottery": "King Lottery",
}


def obtener_html_renderizado():
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            navegador = p.chromium.launch()
            pagina = navegador.new_page()
            pagina.goto(URL, timeout=20000)
            pagina.wait_for_selector("span.text-gray-800", timeout=20000)
            html = pagina.content()
            navegador.close()
            return html, True
    except Exception as e:
        print(f"[aviso] No se pudo obtener {URL} en vivo ({e}). Usando snapshot local.")
        with open(SNAPSHOT_LOCAL, "r", encoding="utf-8") as f:
            return f.read(), False


def extraer_resultados(html):
    """
    Recorre TODOS los bloques de resultado de la portada (no solo los de
    una lotería). Cada juego vive en un <a href="/<empresa>/<juego>/">,
    así que usamos ese href como clave única -- dos loterías distintas
    pueden tener un juego con el mismo nombre (ej. "Loto Pool" existe
    en Leidsa y en Lotería Real), y con el href no se pierden.
    """
    soup = BeautifulSoup(html, "html.parser")
    resultados = []
    vistos = set()

    for bloque in soup.find_all("a", href=True):
        bolas = bloque.find_all("span", class_="text-gray-800")
        if not bolas:
            continue

        href = bloque["href"]
        if href in vistos:
            continue
        vistos.add(href)

        juego_tag = bloque.select_one(".text-xl.font-bold")
        if not juego_tag:
            continue

        fecha_tag = bloque.find(class_="bg-slate-500")
        segmento = href.strip("/").split("/")[0] if href.strip("/") else ""

        resultados.append({
            "empresa": EMPRESAS.get(segmento, segmento or "Otras"),
            "juego": juego_tag.get_text(strip=True),
            "fecha": fecha_tag.get_text(strip=True) if fecha_tag else None,
            "numeros": [b.get_text(strip=True) for b in bolas],
        })

    return resultados


def actualizar_archivo_datos():
    html, en_vivo = obtener_html_renderizado()
    resultados = extraer_resultados(html)

    paquete = {
        "actualizado": datetime.datetime.now().isoformat(timespec="seconds"),
        "en_vivo": en_vivo,
        "resultados": resultados,
    }

    with open(ARCHIVO_DATOS, "w", encoding="utf-8") as f:
        json.dump(paquete, f, ensure_ascii=False, indent=2)

    return paquete


if __name__ == "__main__":
    paquete = actualizar_archivo_datos()
    print(f"Guardado {ARCHIVO_DATOS} con {len(paquete['resultados'])} resultados "
          f"(en_vivo={paquete['en_vivo']}) a las {paquete['actualizado']}")
