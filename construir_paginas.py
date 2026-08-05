# -*- coding: utf-8 -*-
"""
Inyecta los resultados de datos_loteria.json DENTRO del HTML.

Por qué existe este script
--------------------------
Antes las bolas con los números se dibujaban solo con JavaScript, en el
navegador. Eso significa que el HTML que recibe Google llegaba vacío: los
buscadores tenían que ejecutar el JS en una segunda pasada que puede tardar
días. Para una página cuyo valor es la frescura ("resultados de hoy") eso
es fatal.

Ahora este script corre en cada actualización (cada 5 minutos vía GitHub
Actions), lee el JSON y escribe los números directamente en el HTML antes
de subirlo. El JavaScript se queda como estaba, así que el visitante sigue
viendo los datos refrescarse solos entre una construcción y la siguiente.

Uso:  python construir_paginas.py
Salida: carpeta ./publicar/ con el JSON y todas las páginas ya rellenas.
"""

import json
import os
import shutil
import unicodedata
from datetime import datetime, timezone, timedelta

RAIZ = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(RAIZ, "publicar")
JSON_DATOS = os.path.join(RAIZ, "datos_loteria.json")

# Qué archivo corresponde a cada lotería (tal como aparece en el JSON).
PAGINAS_LOTERIA = {
    "loteria-nacional.html": "Lotería Nacional",
    "leidsa.html": "Leidsa",
    "loteria-real.html": "Lotería Real",
    "loteka.html": "Loteka",
    "americanas.html": "Americanas (NY)",
    "la-primera.html": "La Primera",
    "la-suerte.html": "La Suerte",
    "lotedom.html": "LoteDom",
    "anguila.html": "Anguila",
    "king-lottery.html": "King Lottery",
}

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def escapar(texto):
    """Evita que un texto rompa el HTML si trae caracteres especiales."""
    return (str(texto)
            .replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def slug(texto):
    """'Lotería Nacional' -> 'cat-loteria-nacional' (para los anclajes)."""
    base = unicodedata.normalize("NFD", texto.lower())
    base = "".join(c for c in base if unicodedata.category(c) != "Mn")
    limpio = "".join(c if c.isalnum() else "-" for c in base)
    while "--" in limpio:
        limpio = limpio.replace("--", "-")
    return "cat-" + limpio.strip("-")


def fecha_en_texto():
    """Fecha de hoy en horario dominicano (UTC-4), escrita en español."""
    ahora = datetime.now(timezone(timedelta(hours=-4)))
    return "%s %d de %s de %d" % (
        DIAS[ahora.weekday()], ahora.day, MESES[ahora.month - 1], ahora.year)


def tarjeta(item):
    """Una tarjeta de juego con sus bolas de números."""
    bolas = "".join('<div class="bola">%s</div>' % escapar(n)
                    for n in item.get("numeros", []))
    fecha = item.get("fecha") or ""
    return (
        '<div class="card">'
        '<div class="card-header">'
        '<span class="juego">%s</span>'
        '<span class="fecha">%s</span>'
        '</div>'
        '<div class="numeros">%s</div>'
        '</div>'
    ) % (escapar(item.get("juego", "")), escapar(fecha), bolas)


def agrupar(resultados):
    """Agrupa los juegos por empresa, conservando el orden de aparición."""
    grupos = {}
    for item in resultados:
        empresa = item.get("empresa") or "Otras"
        grupos.setdefault(empresa, []).append(item)
    return grupos


def html_portada(resultados):
    """Secciones por lotería + enlaces del menú, para la página principal."""
    secciones, enlaces = [], []
    for empresa, juegos in agrupar(resultados).items():
        ident = slug(empresa)
        enlaces.append('<a href="#%s">%s</a>' % (ident, escapar(empresa)))
        secciones.append(
            '<div class="grupo" id="%s"><h2>%s</h2><div class="grid">%s</div></div>'
            % (ident, escapar(empresa), "".join(tarjeta(j) for j in juegos))
        )
    return "".join(secciones), "".join(enlaces)


def html_una_loteria(resultados, empresa):
    """Solo las tarjetas de una lotería concreta."""
    juegos = [r for r in resultados if r.get("empresa") == empresa]
    if not juegos:
        return ('<p class="cargando">A&uacute;n no hay resultados publicados '
                'para esta loter&iacute;a.</p>')
    return '<div class="grid">%s</div>' % "".join(tarjeta(j) for j in juegos)


def escribir(nombre, contenido):
    destino = os.path.join(SALIDA, nombre)
    with open(destino, "w", encoding="utf-8") as f:
        f.write(contenido)
    print("  %-34s %6d bytes" % (nombre, len(contenido)))


def main():
    if not os.path.exists(JSON_DATOS):
        raise SystemExit("No encuentro datos_loteria.json. "
                         "¿Corrió antes actualizar_datos.py?")

    with open(JSON_DATOS, encoding="utf-8") as f:
        paquete = json.load(f)
    resultados = paquete.get("resultados", [])

    os.makedirs(SALIDA, exist_ok=True)
    shutil.copy(JSON_DATOS, os.path.join(SALIDA, "datos_loteria.json"))

    fecha = "Resultados del %s" % fecha_en_texto()
    print("Construyendo paginas con %d resultados (%s)" % (len(resultados), fecha))

    # --- Portada ---
    ruta_index = os.path.join(RAIZ, "index.html")
    if os.path.exists(ruta_index):
        with open(ruta_index, encoding="utf-8") as f:
            plantilla = f.read()
        secciones, enlaces = html_portada(resultados)
        escribir("index.html", plantilla
                 .replace("<!--RESULTADOS-->", secciones)
                 .replace("<!--NAVLINKS-->", enlaces)
                 .replace("<!--FECHA-->", escapar(fecha)))
    else:
        print("  aviso: no existe index.html, me lo salto")

    # --- Una página por lotería ---
    for archivo, empresa in PAGINAS_LOTERIA.items():
        ruta = os.path.join(RAIZ, archivo)
        if not os.path.exists(ruta):
            print("  aviso: no existe %s, me lo salto" % archivo)
            continue
        with open(ruta, encoding="utf-8") as f:
            plantilla = f.read()
        escribir(archivo, plantilla
                 .replace("<!--RESULTADOS-->", html_una_loteria(resultados, empresa))
                 .replace("<!--FECHA-->", escapar(fecha)))

    print("Listo. Todo en ./publicar/")


if __name__ == "__main__":
    main()
