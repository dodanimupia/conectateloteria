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

import historial as hist

RAIZ = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(RAIZ, "publicar")
JSON_DATOS = os.path.join(RAIZ, "datos_loteria.json")
JSON_HISTORIAL = os.path.join(RAIZ, "historial.json")

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

# Archivos que no se generan: se copian tal cual a "publicar" para que el
# FTP también los suba. Antes quedaban fuera y había que subirlos a mano,
# así que un cambio en el pie de página o en los textos legales no llegaba
# al sitio. Ahora todo viaja en la misma subida.
ARCHIVOS_ESTATICOS = [
    "estilos.css",
    "robots.txt",
    "sitemap.xml",
    # Guías
    "horarios-loterias-dominicanas.html",
    "como-se-juega-la-quiniela.html",
    "que-hacer-si-ganas.html",
    # Páginas legales y de información
    "sobre-nosotros.html",
    "contacto.html",
    "politica-de-privacidad.html",
    "aviso-legal.html",
]

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


def html_historial(historial, empresa, hoy_iso):
    """
    Tabla con los sorteos de los días anteriores, agrupados por juego.

    Es la sección que ningún competidor ofrece: si alguien busca qué salió
    ayer o el lunes pasado, aquí lo encuentra sin tener que rebuscar.
    """
    juegos = hist.por_juego(historial, empresa, hoy_iso)
    if not juegos:
        return ('<p class="cargando">El historial se est&aacute; construyendo. '
                'Vuelve ma&ntilde;ana para ver los resultados de d&iacute;as '
                'anteriores.</p>')

    bloques = []
    for juego, dias in juegos:
        filas = "".join(
            '<tr><td>%s</td><td><div class="numeros numeros-mini">%s</div></td></tr>'
            % (hist.fecha_bonita(f),
               "".join('<div class="bola bola-mini">%s</div>' % escapar(n)
                       for n in numeros))
            for f, numeros in dias
        )
        bloques.append(
            '<h3>%s</h3>'
            '<table class="tabla tabla-historial">'
            '<thead><tr><th>Fecha</th><th>N&uacute;meros ganadores</th></tr></thead>'
            '<tbody>%s</tbody></table>' % (escapar(juego), filas)
        )
    return "".join(bloques)


def html_historial_portada(historial, hoy_iso):
    """
    Historial para la página principal: un bloque plegable por día.

    En la portada están las 10 loterías a la vez, así que mostrar todo
    abierto sería un muro de cientos de números y la página pesaría
    demasiado. Con <details> el contenido sigue estando en el HTML (que es
    lo que Google necesita) pero el visitante solo ve la lista de días y
    abre el que le interesa. Y no hace falta JavaScript.
    """
    dias = hist.dias_ordenados(historial, excluir=hoy_iso)
    if not dias:
        return ('<p class="cargando">El historial se est&aacute; construyendo. '
                'Ma&ntilde;ana aparecer&aacute;n aqu&iacute; los resultados de hoy.</p>')

    bloques = []
    for clave in dias:
        grupos = agrupar(historial["dias"][clave])
        total = sum(len(j) for j in grupos.values())
        cuerpo = []
        for empresa, juegos in grupos.items():
            filas = "".join(
                '<tr><td>%s</td><td><div class="numeros numeros-mini">%s</div></td></tr>'
                % (escapar(j.get("juego", "")),
                   "".join('<div class="bola bola-mini">%s</div>' % escapar(n)
                           for n in j.get("numeros", [])))
                for j in juegos
            )
            cuerpo.append('<h4>%s</h4><table class="tabla tabla-historial">'
                          '<tbody>%s</tbody></table>' % (escapar(empresa), filas))
        bloques.append(
            '<details class="dia-historial">'
            '<summary>%s <span class="cuenta">%d sorteos</span></summary>'
            '<div class="dia-cuerpo">%s</div>'
            '</details>' % (hist.fecha_bonita(clave), total, "".join(cuerpo))
        )
    return "".join(bloques)


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

    # El historial se acumula: guarda lo de hoy y conserva los días previos.
    hoy = datetime.now(timezone(timedelta(hours=-4))).date()
    hoy_iso = hoy.isoformat()
    historial = hist.actualizar(hist.cargar(JSON_HISTORIAL), resultados, hoy)
    hist.guardar(historial, JSON_HISTORIAL)
    print("Historial: %d dias guardados" % len(historial.get("dias", {})))

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
                 .replace("<!--HISTORIAL-->", html_historial_portada(historial, hoy_iso))
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
                 .replace("<!--HISTORIAL-->", html_historial(historial, empresa, hoy_iso))
                 .replace("<!--FECHA-->", escapar(fecha)))

    # --- Archivos que se copian sin modificar ---
    print("Copiando archivos estaticos:")
    for nombre in ARCHIVOS_ESTATICOS:
        origen = os.path.join(RAIZ, nombre)
        if not os.path.exists(origen):
            print("  aviso: falta %s, me lo salto" % nombre)
            continue
        shutil.copy(origen, os.path.join(SALIDA, nombre))
        print("  %-34s copiado" % nombre)

    print("Listo. Todo en ./publicar/")


if __name__ == "__main__":
    main()
