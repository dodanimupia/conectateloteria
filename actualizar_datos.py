"""Obtiene resultados en vivo; un fallo nunca publica la copia de agosto."""

import datetime as dt
import json
import os
from pathlib import Path
import re
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

URL = "https://www.conectate.com.do/loterias/"
ARCHIVO_DATOS = str(Path(__file__).with_name("datos_loteria.json"))
ZONA = ZoneInfo("America/Santo_Domingo")
EMPRESAS = {
    "nacional": "Lotería Nacional", "leidsa": "Leidsa",
    "loto-real": "Lotería Real", "loteka": "Loteka",
    "americanas": "Americanas (NY)", "la-primera": "La Primera",
    "la-suerte-dominicana": "La Suerte", "lotedom": "LoteDom",
    "anguilla": "Anguila", "king-lottery": "King Lottery",
    "haiti-bolet": "Haiti Bolet",
}


def extraer_resultados(html):
    soup = BeautifulSoup(html, "html.parser")
    resultados, vistos = [], set()
    for bloque in soup.find_all("a", href=True):
        ruta = urlparse(bloque["href"]).path.strip("/")
        partes = ruta.split("/")
        if partes and partes[0] == "loterias":
            partes = partes[1:]
        if len(partes) != 2 or partes[0] not in EMPRESAS:
            continue
        clave = "/".join(partes)
        if clave in vistos:
            continue
        nombre = bloque.select_one(".text-xl.font-bold")
        fecha = bloque.select_one(".bg-slate-500")
        bolas = bloque.select("span.text-gray-800")
        numeros = [b.get_text(strip=True) for b in bolas]
        if not nombre or not fecha or not numeros:
            continue
        # Las tarjetas vacías son esqueletos de carga, no resultados.
        if not all(re.fullmatch(r"\d{2}", n) for n in numeros):
            continue
        fecha_texto = fecha.get_text(strip=True)
        if not re.fullmatch(r"\d{2}-\d{2}", fecha_texto):
            continue
        vistos.add(clave)
        resultados.append({
            "empresa": EMPRESAS[partes[0]],
            "juego": " ".join(nombre.get_text(" ", strip=True).split()),
            "fecha": fecha_texto, "numeros": numeros,
        })
    return resultados


def validar_resultados(resultados, ahora=None):
    hoy = (ahora or dt.datetime.now(ZONA)).astimezone(ZONA).date()
    if len(resultados) < 30:
        raise ValueError(f"Fuente incompleta: solo {len(resultados)} sorteos válidos")
    presentes = {r["empresa"] for r in resultados}
    faltantes = set(EMPRESAS.values()) - presentes
    if faltantes:
        raise ValueError("Faltan loterías: " + ", ".join(sorted(faltantes)))
    fechas = []
    for item in resultados:
        dia, mes = map(int, item["fecha"].split("-"))
        fecha = dt.date(hoy.year, mes, dia)
        if fecha > hoy:
            fecha = dt.date(hoy.year - 1, mes, dia)
        if (hoy - fecha).days > 31:
            raise ValueError(f"Sorteo antiguo: {item['juego']} ({item['fecha']})")
        fechas.append(fecha)
    if (hoy - max(fechas)).days > 1:
        raise ValueError("La fuente no contiene resultados de hoy ni de ayer")
    return resultados


def obtener_html_renderizado():
    from playwright.sync_api import sync_playwright

    errores = []
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        try:
            for intento in range(1, 4):
                pagina = navegador.new_page(locale="es-DO", timezone_id="America/Santo_Domingo")
                try:
                    respuesta = pagina.goto(URL, wait_until="domcontentloaded", timeout=60000)
                    if respuesta is None or not respuesta.ok:
                        raise RuntimeError(f"HTTP {respuesta.status if respuesta else 'sin respuesta'}")
                    # Espera números reales y fechas, no solo etiquetas vacías.
                    pagina.wait_for_function("""() => [...document.querySelectorAll('a')]
                      .filter(a => a.querySelector('.text-xl.font-bold')
                        && /^\\d{2}-\\d{2}$/.test(a.querySelector('.bg-slate-500')?.textContent.trim() || '')
                        && a.querySelectorAll('span.text-gray-800').length > 0
                        && [...a.querySelectorAll('span.text-gray-800')]
                          .every(s => /^\\d{2}$/.test(s.textContent.trim()))).length >= 30""",
                      timeout=60000)
                    html = pagina.content()
                    validar_resultados(extraer_resultados(html))
                    return html, True
                except Exception as error:
                    errores.append(str(error))
                    print(f"::warning::Intento {intento}/3 sin datos válidos: {error}")
                finally:
                    pagina.close()
        finally:
            navegador.close()
    raise RuntimeError("No se publicará nada: fallaron los tres intentos de lectura en vivo. " + errores[-1])


def actualizar_archivo_datos():
    html, en_vivo = obtener_html_renderizado()
    if not en_vivo:
        raise ValueError("No se permite publicar un snapshot local")
    ahora = dt.datetime.now(ZONA)
    resultados = validar_resultados(extraer_resultados(html), ahora)
    paquete = {
        "actualizado": ahora.isoformat(timespec="seconds"),
        "zona_horaria": "America/Santo_Domingo", "fuente": URL,
        "en_vivo": True, "resultados": resultados,
    }
    # Reemplazo atómico: el último JSON válido se conserva ante cualquier fallo.
    destino = Path(ARCHIVO_DATOS)
    temporal = destino.with_suffix(".json.tmp")
    temporal.write_text(json.dumps(paquete, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporal, destino)
    return paquete


if __name__ == "__main__":
    try:
        paquete = actualizar_archivo_datos()
    except Exception as error:
        raise SystemExit(f"::error::{error}") from error
    print(f"Guardado {ARCHIVO_DATOS}: {len(paquete['resultados'])} sorteos en vivo, {paquete['actualizado']}")
