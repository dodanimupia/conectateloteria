"""Obtiene resultados en vivo; un fallo nunca publica la copia de agosto."""

import datetime as dt
import json
import os
from pathlib import Path
import re
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

URL = "https://www.conectate.com.do/loterias/"
URL_ALTERNATIVA = "https://www.loteriasdominicanas.com.do/"
URL_API = "https://turifamax.com/api/v1/resultados"
ARCHIVO_DATOS = str(Path(__file__).with_name("datos_loteria.json"))
ZONA = ZoneInfo("America/Santo_Domingo")
AGENTE = "ConectateLoteriaBot/1.0 (+https://github.com/dodanimupia/conectateloteria)"
EMPRESAS = {
    "nacional": "Lotería Nacional", "leidsa": "Leidsa",
    "loto-real": "Lotería Real", "loteka": "Loteka",
    "americanas": "Americanas (NY)", "la-primera": "La Primera",
    "la-suerte-dominicana": "La Suerte", "lotedom": "LoteDom",
    "anguilla": "Anguila", "king-lottery": "King Lottery",
    "haiti-bolet": "Haiti Bolet",
}


def extraer_resultados(html):
    if html.lstrip().startswith("{"):
        datos = json.loads(html)
        if datos.get("origen_api") != URL_API:
            raise ValueError("Origen de API desconocido")
        return datos["resultados"]
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
    if len(resultados) < 20:
        raise ValueError(f"Fuente incompleta: solo {len(resultados)} sorteos válidos")
    presentes = {r["empresa"] for r in resultados}
    faltantes = (set(EMPRESAS.values()) - {"Haiti Bolet"}) - presentes
    if faltantes:
        raise ValueError("Faltan loterías: " + ", ".join(sorted(faltantes)))
    fechas = []
    vistos = set()
    for item in resultados:
        clave = (item["empresa"], item["juego"])
        if clave in vistos or not isinstance(item["juego"], str) or not item["juego"].strip():
            raise ValueError("Juego duplicado o inválido")
        vistos.add(clave)
        numeros = item.get("numeros")
        if not isinstance(numeros, list) or not numeros or not all(
            isinstance(numero, str) and re.fullmatch(r"[0-9]{2}", numero) for numero in numeros
        ):
            raise ValueError(f"Números inválidos: {item['juego']}")
        fecha = fecha_sorteo(item, hoy)
        if item.get("fecha_iso") and item["fecha"] != fecha.strftime("%d-%m"):
            raise ValueError("Fechas inconsistentes")
        if not 0 <= (hoy - fecha).days <= 31:
            raise ValueError(f"Sorteo antiguo: {item['juego']} ({item['fecha']})")
        fechas.append(fecha)
    if (hoy - max(fechas)).days > 1:
        raise ValueError("La fuente no contiene resultados de hoy ni de ayer")
    return resultados


def normalizar_api(registros, todos=False):
    # Identificadores documentados en /api/v1/loterias. Mantiene los
    # nombres del sitio y une las bolas adicionales de la misma fecha.
    catalogo = {
        "nacional": ("Lotería Nacional", "Lotería Nacional", 3, ()),
        "gana-mas": ("Lotería Nacional", "Gana Más", 3, ()),
        "leidsa": ("Leidsa", "Quiniela Leidsa", 3, ()),
        "pega3-mas": ("Leidsa", "Pega 3 Más", 3, ()),
        "super-kino": ("Leidsa", "Super Kino TV", 20, ()),
        "loto-pool": ("Leidsa", "Loto Pool", 5, ()),
        "loto-leidsa": ("Leidsa", "Loto - Loto Más", 6, ("loto-mas", "super-plus")),
        "real": ("Lotería Real", "Quiniela Real", 3, ()),
        "loto-real": ("Lotería Real", "Loto Real", 6, ()),
        "loteka": ("Loteka", "Quiniela Loteka Noche", 3, ()),
        "mega-chances": ("Loteka", "Mega Chances", 5, ()),
        "megalotto": ("Loteka", "MegaLotto", 6, ()),
        "lotedom": ("LoteDom", "LoteDom Día", 3, ()),
        "primera-dia": ("La Primera", "La Primera Día", 3, ()),
        "primera-noche": ("La Primera", "Primera Noche", 3, ()),
        "suerte-tarde": ("La Suerte", "La Suerte Día", 3, ()),
        "suerte-noche": ("La Suerte", "La Suerte Tarde", 3, ()),
        "florida-dia": ("Americanas (NY)", "Florida Día", 3, ()),
        "florida-noche": ("Americanas (NY)", "Florida Noche", 3, ()),
        "ny-tarde": ("Americanas (NY)", "New York Tarde", 3, ()),
        "ny-noche": ("Americanas (NY)", "New York Noche", 3, ()),
        "mega-millions": ("Americanas (NY)", "Mega Millions", 5, ("mega-ball",)),
        "powerball": ("Americanas (NY)", "PowerBall", 5, ("powerball-ball",)),
        "anguila-manana": ("Anguila", "Anguila 10:00 AM", 3, ()),
        "anguila-mediodia": ("Anguila", "Anguila 1:00 PM", 3, ()),
        "anguila-tarde": ("Anguila", "Anguila 6:00 PM", 3, ()),
        "anguila-noche": ("Anguila", "Anguila 9:00 PM", 3, ()),
        "king-tarde": ("King Lottery", "King Lottery Día", 3, ()),
        "king-noche": ("King Lottery", "King Lottery Noche", 3, ()),
    }
    por_fecha = {(r["loteria"], r["fecha"]): r for r in registros}
    ultimos = {}
    historicos = []
    for (clave, fecha_iso), registro in sorted(por_fecha.items(), key=lambda item: item[0][1]):
        if clave not in catalogo:
            continue
        empresa, juego, cantidad, extras = catalogo[clave]
        numeros = registro.get("numeros_texto", [])
        if len(numeros) != cantidad:
            continue
        completo = True
        for extra in extras:
            bola = por_fecha.get((extra, fecha_iso), {}).get("numeros_texto", [])
            if len(bola) != 1:
                completo = False
                break
            numeros = numeros + bola
        if not completo or not all(re.fullmatch(r"\d{2}", n) for n in numeros):
            continue
        fecha = dt.date.fromisoformat(fecha_iso)
        ultimos[clave] = {"empresa": empresa, "juego": juego,
                          "fecha": fecha.strftime("%d-%m"), "fecha_iso": fecha_iso,
                          "numeros": numeros}
        historicos.append(ultimos[clave])
    return historicos if todos else list(ultimos.values())


def obtener_api():
    """Consulta la API sin reintentar denegaciones de acceso ni límites."""
    from urllib.error import HTTPError

    ultimo_error = None
    for intento in range(1, 4):
        try:
            registros = []
            hoy = dt.datetime.now(ZONA).date()
            # Recupera también sorteos semanales y conserva su fecha real.
            for dias in range(14):
                fecha = (hoy - dt.timedelta(days=dias)).isoformat()
                with urlopen(URL_API + "?fecha=" + fecha + "&limite=100", timeout=30) as respuesta:
                    datos = json.load(respuesta)
                if datos.get("ok") is not True or not isinstance(datos.get("resultados"), list):
                    raise ValueError("Respuesta de API inválida")
                registros.extend(datos["resultados"])
            resultados = validar_resultados(normalizar_api(registros))
            return json.dumps({"origen_api": URL_API, "resultados": resultados,
                               "historial_reciente": normalizar_api(registros, todos=True)}), True
        except HTTPError as error:
            ultimo_error = error
            if error.code in (401, 403, 429):
                break
        except (OSError, ValueError, KeyError, TypeError) as error:
            ultimo_error = error
        print(f"::warning::Intento {intento}/3 sin resultados válidos: {ultimo_error}")
    raise RuntimeError("No se publicará nada: la API no devolvió resultados válidos. "
                       + str(ultimo_error))


def obtener_html_publico(url):
    origen = urlparse(url)
    robots_url = f"{origen.scheme}://{origen.netloc}/robots.txt"
    with urlopen(Request(robots_url, headers={"User-Agent": AGENTE}), timeout=30) as respuesta:
        reglas = respuesta.read().decode("utf-8")
    robots = RobotFileParser(robots_url)
    robots.parse(reglas.splitlines())
    if not robots.can_fetch(AGENTE, url):
        raise ValueError(f"robots.txt no permite consultar {url}")
    with urlopen(Request(url, headers={"User-Agent": AGENTE}), timeout=30) as respuesta:
        return respuesta.read().decode(respuesta.headers.get_content_charset() or "utf-8")


def obtener_html_renderizado():
    """Selecciona una fuente accesible y completa antes de publicar."""
    errores = []
    try:
        return obtener_api()
    except (RuntimeError, OSError, ValueError, KeyError, TypeError) as error:
        errores.append(f"{URL_API}: {error}")
        print(f"::warning::API no disponible: {error}")
    for url in (URL_ALTERNATIVA, URL):
        try:
            html = obtener_html_publico(url)
            validar_resultados(extraer_resultados(html))
            print(f"Fuente pública validada: {url}")
            return html, True
        except (OSError, ValueError, KeyError, TypeError) as error:
            errores.append(f"{url}: {error}")
            print(f"::warning::Fuente no disponible: {url}: {error}")
    raise RuntimeError("Ninguna fuente válida; se conservan los archivos existentes. "
                       + " | ".join(errores))


def conservar_historial_reciente(recientes, resultados, ahora):
    try:
        anterior = json.loads(Path(ARCHIVO_DATOS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        anterior = {}
    historicos = {}
    guardados = anterior.get("historial_reciente", []) if anterior.get("en_vivo") is True else []
    for item in guardados + recientes + resultados:
        try:
            fecha = fecha_sorteo(item, ahora.date())
            if not 0 <= (ahora.date() - fecha).days < 14:
                continue
            numeros = item["numeros"]
            if not isinstance(numeros, list) or not numeros or not all(
                isinstance(numero, str) and re.fullmatch(r"[0-9]{2}", numero) for numero in numeros
            ):
                continue
            clave = (fecha.isoformat(), item["empresa"], item["juego"])
            historicos[clave] = dict(item, fecha_iso=fecha.isoformat())
        except (KeyError, TypeError, ValueError):
            continue
    return list(historicos.values())


def actualizar_archivo_datos():
    html, en_vivo = obtener_html_renderizado()
    if not en_vivo:
        raise ValueError("No se permite publicar un snapshot local")
    ahora = dt.datetime.now(ZONA)
    resultados = validar_resultados(extraer_resultados(html), ahora)
    fuente = URL_API if html.lstrip().startswith("{") else (
        URL_ALTERNATIVA if "data-resultados-esperados" in html else URL)
    resultados = conservar_sorteos_ausentes(resultados, fuente, ahora)
    validar_resultados(resultados, ahora)
    paquete = {
        "actualizado": ahora.isoformat(timespec="seconds"),
        "zona_horaria": "America/Santo_Domingo", "fuente": fuente,
        "en_vivo": True, "resultados": resultados,
        "historial_reciente": conservar_historial_reciente(
            json.loads(html).get("historial_reciente", []) if fuente == URL_API else [],
            resultados, ahora),
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
