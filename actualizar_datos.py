"""Obtiene resultados en vivo; un fallo nunca publica la copia de agosto."""

import datetime as dt
import json
import os
from pathlib import Path
import re
from urllib.parse import urlparse
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

URL = "https://www.conectate.com.do/loterias/"
URL_ALTERNATIVA = "https://www.loteriasdominicanas.com.do/"
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
    if soup.select_one("article.draw-item[data-fecha-resultado]"):
        return extraer_fuente_alternativa(soup)
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


def extraer_fuente_alternativa(soup):
    grupos = {
        "Nacional": "Lotería Nacional", "Leidsa": "Leidsa", "Real": "Lotería Real",
        "Loteka": "Loteka", "Americanas": "Americanas (NY)", "La Primera": "La Primera",
        "La Suerte": "La Suerte", "Lotedom": "LoteDom", "Lotería Anguila": "Anguila",
        "King Lottery": "King Lottery", "Haiti": "Haiti Bolet",
    }
    nombres = {
        "Gana Mas": "Gana Más", "Quiniela Nacional": "Lotería Nacional",
        "Juega mas Pega mas": "Juega + Pega +", "Pega 3 Mas": "Pega 3 Más",
        "Quiniela Pale": "Quiniela Leidsa", "Loto Pool Leidsa": "Loto Pool",
        "Loto Mas": "Loto - Loto Más", "Quiniela Real Noche": "Lotería Real Noche",
        "Loto Pool Real": "Loto Pool", "Quiniela Loteka": "Quiniela Loteka Noche",
        "MegaChance": "Mega Chances", "Florida Tarde": "Florida Día",
        "La Primera Mediodia": "La Primera Día", "La Primera Noche": "Primera Noche",
        "La Suerte Mediodia": "La Suerte Día", "La Suerte Noche": "La Suerte Tarde",
        "Quiniela Lotedom": "LoteDom Día", "Quemaito Mayor": "El Quemaito Mayor",
        "Súper Palé": "Super Palé Día", "SXM Quiniela Día": "King Lottery Día",
        "SXM Quiniela Noche": "King Lottery Noche",
    }
    resultados = []
    for grupo in soup.select("section.lottery-group"):
        titulo = grupo.select_one("h2")
        empresa = grupos.get(titulo.get_text(" ", strip=True) if titulo else "")
        if not empresa:
            continue
        for card in grupo.select("article.draw-item[data-fecha-resultado]"):
            fecha = dt.date.fromisoformat(card["data-fecha-resultado"])
            numeros = [b.get_text(strip=True) for b in card.select(".balls .ball")]
            esperados = int(card.get("data-resultados-esperados", "0"))
            if len(numeros) != esperados or not numeros or not all(re.fullmatch(r"\d{2}", n) for n in numeros):
                continue
            nombre = card.get("data-share-sorteo", "").strip()
            if not nombre:
                continue
            resultados.append({"empresa": empresa, "juego": nombres.get(nombre, nombre),
                               "fecha": fecha.strftime("%d-%m"), "fecha_iso": fecha.isoformat(),
                               "numeros": numeros})
    return resultados


def fecha_sorteo(item, hoy):
    if item.get("fecha_iso"):
        return dt.date.fromisoformat(item["fecha_iso"])
    dia, mes = map(int, item["fecha"].split("-"))
    fecha = dt.date(hoy.year, mes, dia)
    return fecha if fecha <= hoy else dt.date(hoy.year - 1, mes, dia)


def conservar_sorteos_ausentes(resultados, fuente, ahora):
    # Una fuente puede cubrir más horarios que otra: no borres sorteos
    # recientes ya verificados ni reemplaces una fecha nueva por otra vieja.
    hoy = ahora.date()
    nuevos = {(r["empresa"], r["juego"]): dict(r, fuente=fuente) for r in resultados}
    try:
        anterior = json.loads(Path(ARCHIVO_DATOS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return list(nuevos.values())
    if anterior.get("en_vivo") is not True:
        return list(nuevos.values())
    for item in anterior.get("resultados", []):
        try:
            fecha = fecha_sorteo(item, hoy)
            if not 0 <= (hoy - fecha).days <= 7:
                continue
            clave = (item["empresa"], item["juego"])
            if clave not in nuevos or fecha > fecha_sorteo(nuevos[clave], hoy):
                nuevos[clave] = dict(item, fuente=item.get("fuente", anterior.get("fuente", URL)))
        except (KeyError, TypeError, ValueError):
            continue
    return list(nuevos.values())


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
        fecha = fecha_sorteo(item, hoy)
        if not 0 <= (hoy - fecha).days <= 31:
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
                        raise PermissionError(f"HTTP {respuesta.status if respuesta else 'sin respuesta'}")
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
                except PermissionError as error:
                    errores.append(str(error))
                    print(f"::warning::La fuente principal denegó la consulta: {error}")
                    break
                except Exception as error:
                    errores.append(str(error))
                    print(f"::warning::Intento {intento}/3 sin datos válidos: {error}")
                finally:
                    pagina.close()
        finally:
            navegador.close()
    # Fuente pública independiente: HTTPS normal, sin proxies ni evasión.
    print("Consultando fuente pública alternativa: " + URL_ALTERNATIVA)
    try:
        with urlopen(URL_ALTERNATIVA, timeout=45) as respuesta:
            html = respuesta.read().decode("utf-8")
        validar_resultados(extraer_resultados(html))
        return html, True
    except Exception as error:
        raise RuntimeError("No se publicará nada: ninguna fuente devolvió datos válidos. " + str(error)) from error


def actualizar_archivo_datos():
    html, en_vivo = obtener_html_renderizado()
    if not en_vivo:
        raise ValueError("No se permite publicar un snapshot local")
    ahora = dt.datetime.now(ZONA)
    resultados = validar_resultados(extraer_resultados(html), ahora)
    fuente = URL_ALTERNATIVA if "data-resultados-esperados" in html else URL
    resultados = conservar_sorteos_ausentes(resultados, fuente, ahora)
    validar_resultados(resultados, ahora)
    paquete = {
        "actualizado": ahora.isoformat(timespec="seconds"),
        "zona_horaria": "America/Santo_Domingo", "fuente": fuente,
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
