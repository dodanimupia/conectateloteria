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
import re
import shutil
import unicodedata
from datetime import date, datetime, timezone, timedelta

import historial as hist

RAIZ = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(RAIZ, "publicar")
JSON_DATOS = os.path.join(RAIZ, "datos_loteria.json")
JSON_HISTORIAL = os.path.join(RAIZ, "historial.json")
DOMINIO = "https://conectateloteria.com/"

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
    ".htaccess",      # reglas de cache: sin esto el navegador sirve paginas viejas
    "estilos.css",
    "robots.txt",
    "ads.txt",       # AdSense lo exige en la raiz del dominio
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

# La fuente a veces entrega el identificador interno en vez del nombre.
# Aqui se traduce a algo presentable antes de mostrarlo.
NOMBRES_BONITOS = {
    "haiti-bolet": "Haiti Bolet",
}

# Orden en que se muestran las loterias. Sin esto salen en el orden en que
# la fuente las devuelve, que cambia de un dia a otro y hace que el
# historial se vea desordenado al compararlo entre fechas.
ORDEN_EMPRESAS = [
    "Loteria Nacional", "Lotería Nacional", "Leidsa", "Lotería Real",
    "Loteka", "La Primera", "La Suerte", "LoteDom", "Anguila",
    "King Lottery", "Haiti Bolet", "Americanas (NY)",
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
    # Algunos sorteos llegan sin fecha desde la fuente. En ese caso no se
    # pinta la pastilla: una pastilla vacia se ve como un error.
    fecha = item.get("fecha") or ""
    pastilla = ('<span class="fecha">%s</span>' % escapar(fecha)) if fecha else ""
    return (
        '<div class="card">'
        '<div class="card-header">'
        '<span class="juego">%s</span>'
        '%s'
        '</div>'
        '<div class="numeros">%s</div>'
        '</div>'
    ) % (escapar(item.get("juego", "")), pastilla, bolas)


def nombre_empresa(bruto):
    """Traduce el identificador de la fuente al nombre que se muestra."""
    limpio = " ".join(str(bruto or "").split()) or "Otras"
    return NOMBRES_BONITOS.get(limpio, limpio)


def agrupar(resultados, ordenar=False):
    """
    Agrupa los juegos por loteria.

    Con ordenar=True las loterias salen siempre en el mismo orden y los
    juegos de cada una ordenados por hora. Eso es lo que hace que el
    historial se pueda comparar de un dia a otro sin marearse.
    """
    grupos = {}
    for item in resultados:
        grupos.setdefault(nombre_empresa(item.get("empresa")), []).append(item)

    if not ordenar:
        return grupos

    def puesto(nombre):
        return (ORDEN_EMPRESAS.index(nombre)
                if nombre in ORDEN_EMPRESAS else len(ORDEN_EMPRESAS))

    ordenado = {}
    for empresa in sorted(grupos, key=lambda e: (puesto(e), e)):
        ordenado[empresa] = sorted(
            grupos[empresa], key=lambda j: hist.orden_juego(j.get("juego", "")))
    return ordenado


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
    """Texto propio de la lotería más las tarjetas de sus juegos."""
    intro = html_texto_loteria(empresa)
    juegos = [r for r in resultados if r.get("empresa") == empresa]
    if not juegos:
        return intro + ('<p class="cargando">A&uacute;n no hay resultados '
                        'publicados para esta loter&iacute;a.</p>')
    return intro + ('<div class="grid">%s</div>'
                    % "".join(tarjeta(j) for j in juegos))


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
            % (hist.fecha_bonita(f, date.fromisoformat(hoy_iso)),
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

    hoy = date.fromisoformat(hoy_iso)
    bloques = []
    for clave in dias:
        grupos = agrupar(historial["dias"][clave], ordenar=True)
        total = sum(len(j) for j in grupos.values())

        cuerpo = []
        for empresa, juegos in grupos.items():
            filas = "".join(
                '<li><span class="hj-juego">%s</span>'
                '<span class="numeros numeros-mini">%s</span></li>'
                % (escapar(hist.limpiar_nombre(j.get("juego", ""))),
                   "".join('<span class="bola bola-mini">%s</span>' % escapar(n)
                           for n in j.get("numeros", [])))
                for j in juegos
            )
            cuerpo.append(
                '<div class="hj-loteria">'
                '<h4>%s <span class="hj-cuenta">%d</span></h4>'
                '<ul class="hj-lista">%s</ul>'
                '</div>' % (escapar(empresa), len(juegos), filas)
            )

        bloques.append(
            '<details class="dia-historial">'
            '<summary><span class="dia-nombre">%s</span>'
            '<span class="cuenta">%d %s</span></summary>'
            '<div class="dia-cuerpo">%s'
            '<p class="ver-dia"><a href="%s">Ver la p&aacute;gina de este d&iacute;a &rarr;</a></p>'
            '</div>'
            '</details>'
            % (escapar(hist.fecha_bonita(clave, hoy)), total,
               "sorteo" if total == 1 else "sorteos", "".join(cuerpo),
               ruta_dia(clave))
        )
    return "".join(bloques)


def escribir(nombre, contenido):
    destino = os.path.join(SALIDA, nombre)
    with open(destino, "w", encoding="utf-8") as f:
        f.write(contenido)
    print("  %-34s %6d bytes" % (nombre, len(contenido)))


# --- Texto propio de cada loteria ---------------------------------------
# Sin esto cada pagina de loteria era la misma plantilla con numeros
# distintos. Un buscador (y un revisor de AdSense) lo lee como contenido
# duplicado. Cada entrada describe una loteria concreta: que juegos tiene,
# a que hora sortea y que conviene saber para leer sus resultados.
TEXTO_LOTERIA = {
    "Lotería Nacional": (
        "La Lotería Nacional es la lotería estatal dominicana y la más "
        "antigua del país: lleva sorteándose desde 1930. Es la única "
        "operada directamente por el Estado, y sus beneficios se destinan "
        "por ley a programas sociales.",
        "En esta página verás tres juegos distintos. El sorteo principal, "
        "que también se llama Lotería Nacional, reparte tres números de dos "
        "cifras: el primero es el premio mayor, y el segundo y el tercero "
        "son las llamadas segunda y tercera. Gana Más es una quiniela con "
        "sorteos de lunes a sábado, y Juega + Pega + añade una modalidad de "
        "cinco números con premios por aciertos parciales.",
    ),
    "Leidsa": (
        "Leidsa es la lotería privada con más juegos en una sola tanda del "
        "país, y por eso su sorteo nocturno es de los más seguidos: en una "
        "misma emisión salen desde la quiniela clásica hasta loterías de "
        "pozo acumulado que pueden arrastrarse durante semanas.",
        "Aquí encontrarás la Quiniela Leidsa, de tres números; Pega 3 Más, "
        "que exige acertar el orden; Loto Pool, con cinco números; Super "
        "Kino TV, que saca veinte números de una vez y se juega marcando "
        "cuántos quieras de ellos; y Loto - Loto Más, el juego de pozo "
        "acumulado que reparte los premios más grandes. Cada uno tiene su "
        "propia estructura de premios, así que conviene mirar el nombre del "
        "juego y no solo los números.",
    ),
    "Lotería Real": (
        "Lotería Real empezó como una banca regional y hoy sortea a diario "
        "en todo el país. Su tanda de la tarde la convierte en una de las "
        "primeras loterías grandes del día, antes de que salgan las "
        "nocturnas.",
        "En esta página se publican la Quiniela Real, de tres números; Loto "
        "Pool, con cuatro; Nueva Yol Real, que replica el formato de las "
        "americanas; y Loto Real, el sorteo de pozo acumulado con seis "
        "números que solo se juega algunos días de la semana. Si un juego "
        "no aparece con la fecha de hoy, es porque ese día no le toca "
        "sorteo.",
    ),
    "Loteka": (
        "Loteka fue una de las primeras loterías privadas dominicanas en "
        "apostar por los juegos de pozo acumulado. Sortea a las 7:55 de la "
        "noche, justo antes que Leidsa, así que mucha gente sigue las dos "
        "tandas seguidas.",
        "Publicamos aquí la Quiniela Loteka, de tres números, y Mega "
        "Chances, que saca cinco números y admite premios por aciertos "
        "parciales. Loteka también organiza sorteos especiales en fechas "
        "señaladas; cuando los hay, aparecen en esta misma lista con su "
        "nombre propio.",
    ),
    "Americanas (NY)": (
        "Las llamadas americanas no son loterías dominicanas: son sorteos "
        "de Estados Unidos que las bancas del país ofrecen igualmente. Se "
        "siguen tanto como las locales porque suman varias tandas al día y "
        "porque los pozos de PowerBall y Mega Millions llegan a cifras que "
        "ninguna lotería dominicana alcanza.",
        "Verás aquí New York Tarde y New York Noche, que son quinielas de "
        "tres números; Florida Día y Florida Noche, con el mismo formato; y "
        "los dos grandes acumulados, PowerBall y Mega Millions, que sortean "
        "solo unos días por semana. Ten en cuenta el horario: al salir en "
        "Estados Unidos, los resultados de la noche pueden publicarse ya "
        "entrada la madrugada en República Dominicana.",
    ),
    "La Primera": (
        "La Primera debe su nombre al horario: durante años fue la primera "
        "tanda del día en salir, cuando casi todas las demás sorteaban de "
        "noche. Hoy mantiene sorteos de día y de noche.",
        "En esta página aparecen La Primera Día y Primera Noche, ambas "
        "quinielas de tres números, y Loto 5, un juego de cinco números más "
        "uno adicional. Si buscas el resultado de una tanda concreta, "
        "fíjate en el nombre del juego: el de la mañana y el de la noche se "
        "publican por separado.",
    ),
    "La Suerte": (
        "La Suerte Dominicana es una de las bancas más extendidas en el "
        "interior del país. Sus dos tandas diarias, de día y de tarde, la "
        "hacen popular entre quienes juegan antes de que salgan las "
        "loterías nocturnas.",
        "Aquí se publican La Suerte Día y La Suerte Tarde, las dos "
        "quinielas de tres números. Al ser sorteos cortos, sus resultados "
        "suelen aparecer pocos minutos después de la hora del sorteo.",
    ),
    "LoteDom": (
        "LoteDom combina una quiniela tradicional con El Quemaito Mayor, un "
        "juego de un solo número que es su sello propio y no tiene "
        "equivalente en las demás loterías dominicanas.",
        "El Quemaito Mayor saca una sola cifra, así que su casilla se ve "
        "distinta al resto: una bola en lugar de tres. La quiniela LoteDom "
        "funciona como las demás, con premio mayor, segunda y tercera. "
        "Ambos sorteos se publican aquí en cuanto la fuente los emite.",
    ),
    "Anguila": (
        "Anguila es, con diferencia, la lotería con más sorteos al día de "
        "las que se juegan en República Dominicana: sortea cada hora, desde "
        "la mañana hasta la noche. Toma su nombre de la isla de Anguila, en "
        "el Caribe oriental.",
        "Por eso esta página muestra muchas más casillas que las demás: una "
        "por cada tanda horaria, desde las 8:00 AM hasta las 10:00 PM. "
        "Están ordenadas por hora, de la mañana a la noche, para que "
        "encuentres rápido la que buscas. Todas son quinielas de tres "
        "números. Si una tanda todavía no aparece, es que aún no se ha "
        "sorteado o la fuente no la ha publicado.",
    ),
    "King Lottery": (
        "King Lottery se sortea en San Martín y llega a República "
        "Dominicana a través de las bancas, igual que las americanas. Tiene "
        "dos tandas diarias, una de día y otra de noche.",
        "En esta página verás King Lottery Día y King Lottery Noche, las "
        "dos quinielas de tres números. Al tratarse de una lotería de "
        "fuera, sus horarios de publicación pueden variar unos minutos "
        "respecto a las dominicanas.",
    ),
    "Haiti Bolet": (
        "Haiti Bolet recoge los sorteos de la lotería haitiana, muy "
        "seguidos en la zona fronteriza y en las bancas dominicanas que "
        "ofrecen ambos mercados.",
        "Sortea varias veces al día, con tandas de mañana, mediodía y "
        "noche. Cada casilla lleva la hora del sorteo en el nombre para que "
        "no se confundan entre sí.",
    ),
}


def html_texto_loteria(empresa):
    """Parrafos propios de una loteria, si los tenemos escritos."""
    parrafos = TEXTO_LOTERIA.get(empresa)
    if not parrafos:
        return ""
    return ('<div class="intro-loteria">%s</div>'
            % "".join("<p>%s</p>" % escapar(p) for p in parrafos))


# --- Piezas compartidas con la portada ----------------------------------
# Las paginas nuevas (dias y estadisticas) reutilizan el estilo, la barra
# de arriba y el pie de index.html en vez de copiarlos. Asi un cambio de
# diseno se propaga solo y no hay tres versiones del mismo CSS.
def piezas_comunes(plantilla):
    estilo = re.search(r"<style>[\s\S]*?</style>", plantilla).group(0)
    barra = re.search(r'<nav class="navbar"[\s\S]*?</nav>', plantilla).group(0)
    pie = re.search(r"<footer[\s\S]*?</footer>", plantilla).group(0)
    enlaces = "".join('<a href="%s">%s</a>' % (a, escapar(n))
                      for a, n in PAGINAS_LOTERIA.items())
    barra = barra.replace("<!--NAVLINKS-->", enlaces)
    return estilo, barra, pie


GUION_MENU = """<script>
(function () {
  var boton = document.getElementById("menu-toggle");
  var panel = document.getElementById("nav-links");
  if (!boton || !panel) return;
  boton.addEventListener("click", function (e) {
    e.stopPropagation();
    var abierto = panel.classList.toggle("abierto");
    boton.setAttribute("aria-expanded", abierto ? "true" : "false");
  });
  document.addEventListener("click", function (e) {
    if (!panel.contains(e.target) && e.target !== boton) {
      panel.classList.remove("abierto");
      boton.setAttribute("aria-expanded", "false");
    }
  });
})();
</script>"""


def pagina(titulo, descripcion, ruta, cuerpo, piezas, extra_head=""):
    """Arma una pagina completa con la misma cara que el resto del sitio."""
    estilo, barra, pie = piezas
    return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>%s</title>
<meta name="description" content="%s">
<meta name="robots" content="index, follow">
<link rel="canonical" href="%s%s">
<meta property="og:type" content="website">
<meta property="og:title" content="%s">
<meta property="og:description" content="%s">
<meta property="og:url" content="%s%s">
<link rel="icon" type="image/png" href="png/icono.png">
%s
%s
</head>
<body>
%s
<section class="resultados">
  <div class="contenedor">
%s
  </div>
</section>
%s
%s
</body>
</html>
""" % (escapar(titulo), escapar(descripcion), DOMINIO, ruta,
       escapar(titulo), escapar(descripcion), DOMINIO, ruta,
       extra_head, estilo, barra, cuerpo, pie, GUION_MENU)

# --- Paginas de un dia --------------------------------------------------
def ruta_dia(iso):
    return "resultados-%s.html" % iso


def html_sorteos_del_dia(historial, clave):
    """Los sorteos de una fecha, agrupados por loteria."""
    partes = []
    for empresa, juegos in por_empresa(historial["dias"].get(clave, [])):
        filas = "".join(
            '<li><span class="hj-juego">%s</span>'
            '<span class="numeros numeros-mini">%s</span></li>'
            % (escapar(j.get("juego", "")),
               "".join('<span class="bola bola-mini">%s</span>' % escapar(n)
                       for n in j.get("numeros", [])))
            for j in juegos)
        partes.append(
            '<div class="hj-loteria"><h3>%s <span class="hj-cuenta">%d</span></h3>'
            '<ul class="hj-lista">%s</ul></div>'
            % (escapar(empresa), len(juegos), filas))
    return "".join(partes) or "<p>No se guardaron sorteos de esta fecha.</p>"


def por_empresa(sorteos):
    """Agrupa los sorteos de un dia y los devuelve en el orden habitual."""
    grupos = {}
    for s in sorteos:
        grupos.setdefault(nombre_empresa(s.get("empresa", "")), []).append(s)
    def puesto(par):
        try:
            return (0, ORDEN_EMPRESAS.index(par[0]))
        except ValueError:
            return (1, 0)
    for empresa in grupos:
        grupos[empresa].sort(key=lambda s: hist.orden_juego(s.get("juego", "")))
    return sorted(grupos.items(), key=puesto)


def escribir_paginas_de_dia(historial, hoy_iso, piezas):
    """
    Una pagina por fecha guardada.

    El historial vivia dentro de un desplegable de la portada: siete dias
    de datos sin direccion propia, invisibles para un buscador. Con una
    pagina por fecha, cada dia puede aparecer en resultados de busqueda
    y el sitio suma una pagina nueva cada jornada sin tocar nada.
    """
    claves = sorted(historial.get("dias", {}).keys(), reverse=True)
    hechas = []
    for i, clave in enumerate(claves):
        sorteos = historial["dias"][clave]
        if not sorteos:
            continue
        bonita = hist.fecha_bonita(clave, date.fromisoformat(hoy_iso))
        titulo_dia = bonita[0].upper() + bonita[1:]
        if titulo_dia.startswith("Ayer, "):
            titulo_dia = titulo_dia[6].upper() + titulo_dia[7:]
        anio = clave[:4]

        # Enlaces al dia anterior y al siguiente: encadenan las paginas
        # entre si para que el robot llegue a todas desde cualquiera.
        navegacion = []
        if i + 1 < len(claves):
            navegacion.append('<a class="salto" href="%s">&larr; Día anterior</a>'
                              % ruta_dia(claves[i + 1]))
        navegacion.append('<a class="salto" href="./">Resultados de hoy</a>')
        if i > 0:
            navegacion.append('<a class="salto" href="%s">Día siguiente &rarr;</a>'
                              % ruta_dia(claves[i - 1]))

        otras = "".join('<li><a href="%s">%s</a></li>'
                        % (ruta_dia(c), escapar(hist.fecha_bonita(c)))
                        for c in claves if c != clave)

        cuerpo = """    <p class="miga"><a href="./">Inicio</a> &rsaquo; Resultados por fecha</p>
    <h1>Resultados de las loterías del %s de %s</h1>
    <p class="entradilla">Estos son los %d sorteos que se publicaron el %s:
    quiniela, pega 3, loto pool y el resto de los juegos de las loterías
    dominicanas, ordenados por lotería y por hora del sorteo.</p>
    <div class="dia-cuerpo suelto">%s</div>
    <p class="nota-dia">Los números de esta página quedan fijos: son los que
    salieron ese día. Para los sorteos de hoy, mira la
    <a href="./">portada</a>. Antes de reclamar un premio, compara siempre
    con el resultado oficial de la banca.</p>
    <nav class="saltos">%s</nav>
    <h2>Otros días guardados</h2>
    <ul class="lista-dias">%s</ul>
""" % (escapar(titulo_dia), anio, len(sorteos), escapar(titulo_dia),
       html_sorteos_del_dia(historial, clave), "".join(navegacion), otras)

        titulo = "Resultados de las loterías del %s de %s" % (titulo_dia, anio)
        descripcion = ("Todos los números que salieron el %s de %s en las "
                       "loterías dominicanas: Nacional, Leidsa, Real, Loteka, "
                       "La Primera, Anguila y más." % (titulo_dia, anio))
        escribir(ruta_dia(clave),
                 pagina(titulo, descripcion, ruta_dia(clave), cuerpo, piezas))
        hechas.append(clave)
    print("  %-34s %d paginas" % ("resultados-<fecha>.html", len(hechas)))
    return hechas

# --- Estadisticas -------------------------------------------------------
RUTA_ESTADISTICAS = "estadisticas.html"


def contar_numeros(historial, solo_empresa=None):
    """Cuenta cuantas veces salio cada numero en el historial guardado."""
    cuenta = {}
    for sorteos in historial.get("dias", {}).values():
        for s in sorteos:
            if solo_empresa and nombre_empresa(s.get("empresa", "")) != solo_empresa:
                continue
            for n in s.get("numeros", []):
                n = str(n).strip()
                if n:
                    cuenta[n] = cuenta.get(n, 0) + 1
    return cuenta


def tabla_frecuencias(cuenta, cuantos=12, mayor=True):
    if not cuenta:
        return "<p>Todavía no hay suficientes sorteos guardados.</p>"
    orden = sorted(cuenta.items(), key=lambda p: (-p[1], p[0]) if mayor else (p[1], p[0]))
    total = sum(cuenta.values())
    filas = "".join(
        '<li><span class="bola bola-mini">%s</span>'
        '<span class="frec-veces">%d %s</span>'
        '<span class="frec-pct">%.1f%%</span></li>'
        % (escapar(n), v, "vez" if v == 1 else "veces", 100.0 * v / total)
        for n, v in orden[:cuantos])
    return '<ul class="frecuencias">%s</ul>' % filas


def escribir_estadisticas(historial, piezas):
    """
    Numeros mas y menos repetidos del historial que llevamos guardado.

    Se dice con todas las letras cuantos dias abarca y que no sirve para
    predecir: cada sorteo es independiente. Prometer lo contrario seria
    mentir y ademas es lo que hace que a estas paginas se las tome por
    basura.
    """
    dias = sorted(historial.get("dias", {}).keys())
    if not dias:
        return None
    total_sorteos = sum(len(v) for v in historial["dias"].values())
    general = contar_numeros(historial)

    bloques = []
    for empresa in ORDEN_EMPRESAS:
        cuenta = contar_numeros(historial, empresa)
        if len(cuenta) < 5:
            continue
        bloques.append(
            '<div class="hj-loteria"><h3>%s</h3>%s</div>'
            % (escapar(empresa), tabla_frecuencias(cuenta, 6)))

    cuerpo = """    <p class="miga"><a href="./">Inicio</a> &rsaquo; Estadísticas</p>
    <h1>Números más salidos en las loterías dominicanas</h1>
    <p class="entradilla">Recuento de los números que más y menos se han
    repetido en los %d sorteos que llevamos guardados, entre el %s y el %s.
    La cuenta se rehace sola cada vez que se publica un sorteo nuevo.</p>

    <div class="aviso-honesto">
      <p><strong>Antes de seguir:</strong> esto no sirve para predecir nada.
      Cada sorteo es independiente del anterior y todos los números tienen
      siempre la misma probabilidad de salir. Que un número se haya repetido
      mucho no lo hace más ni menos probable mañana. Publicamos el recuento
      porque es un dato curioso sobre lo ya ocurrido, no como método para
      acertar.</p>
    </div>

    <h2>Los más repetidos</h2>
    %s
    <h2>Los menos repetidos</h2>
    %s
    <h2>Por lotería</h2>
    <p>Mismo recuento, separado por cada lotería:</p>
    <div class="dia-cuerpo suelto">%s</div>
    <p class="nota-dia">La muestra es pequeña y crece cada día. Con pocos
    sorteos las diferencias entre un número y otro son casualidad, no
    tendencia. Puedes ver los sorteos completos, día por día, en la
    <a href="./">portada</a>.</p>
""" % (total_sorteos, escapar(hist.fecha_bonita(dias[0])),
       escapar(hist.fecha_bonita(dias[-1])),
       tabla_frecuencias(general, 12, True),
       tabla_frecuencias(general, 12, False),
       "".join(bloques))

    titulo = "Números más salidos en las loterías dominicanas | Estadísticas"
    descripcion = ("Qué números se repiten más y menos en la quiniela y demás "
                   "sorteos dominicanos, con el recuento actualizado de los "
                   "últimos días. Explicado sin promesas de acertar.")
    escribir(RUTA_ESTADISTICAS,
             pagina(titulo, descripcion, RUTA_ESTADISTICAS, cuerpo, piezas))
    print("  %-34s %d sorteos" % (RUTA_ESTADISTICAS, total_sorteos))
    return RUTA_ESTADISTICAS


# --- Sitemap -----------------------------------------------------------
# La fecha de estas paginas va escrita a mano a proposito. En GitHub Actions
# el repositorio se descarga de cero cada vez, asi que la fecha de
# modificacion del archivo seria la de hoy aunque el texto lleve semanas
# igual: justo la mentira que hace que Google deje de fiarse del sitemap.
# Al tocar una de estas paginas, actualiza su fecha aqui.
PAGINAS_FIJAS = [
    ("horarios-loterias-dominicanas.html", "2026-08-05", "monthly", "0.6"),
    ("como-se-juega-la-quiniela.html", "2026-08-05", "monthly", "0.6"),
    ("que-hacer-si-ganas.html", "2026-08-05", "monthly", "0.6"),
    ("sobre-nosotros.html", "2026-08-05", "yearly", "0.3"),
    ("contacto.html", "2026-08-05", "yearly", "0.3"),
    ("politica-de-privacidad.html", "2026-08-05", "yearly", "0.2"),
    ("aviso-legal.html", "2026-08-05", "yearly", "0.2"),
]


def escribir_sitemap(hoy_iso, dias=(), extras=()):
    """
    Genera sitemap.xml con la fecha de hoy en las paginas de resultados.

    Antes el sitemap era un archivo fijo con una fecha escrita a mano. Al
    quedarse congelada mientras el contenido si cambiaba, Google acaba
    ignorando el <lastmod>. Ahora la portada y las paginas de loteria
    llevan la fecha real de esta construccion; las guias y legales
    conservan la suya, que es la verdad.
    """
    partes = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']

    def url(loc, lastmod, freq, prioridad):
        partes.append("  <url>")
        partes.append("    <loc>%s%s</loc>" % (DOMINIO, loc))
        partes.append("    <lastmod>%s</lastmod>" % lastmod)
        partes.append("    <changefreq>%s</changefreq>" % freq)
        partes.append("    <priority>%s</priority>" % prioridad)
        partes.append("  </url>")

    url("", hoy_iso, "hourly", "1.0")
    for archivo in PAGINAS_LOTERIA:
        url(archivo, hoy_iso, "hourly", "0.9")

    for ruta in extras:
        url(ruta, hoy_iso, "daily", "0.7")

    # Cada dia ya paso: su contenido no vuelve a cambiar.
    for clave in dias:
        url(ruta_dia(clave), clave, "monthly", "0.5")

    for archivo, modificado, freq, prioridad in PAGINAS_FIJAS:
        if not os.path.exists(os.path.join(RAIZ, archivo)):
            continue
        url(archivo, modificado, freq, prioridad)

    partes.append("</urlset>")
    partes.append("")
    escribir("sitemap.xml", "\n".join(partes))
    print("  %-34s %d URLs" % ("sitemap.xml", (len(partes) - 3) // 6))


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

    fecha = "Resultados de hoy, %s" % fecha_en_texto()
    print("Construyendo paginas con %d resultados (%s)" % (len(resultados), fecha))

    # --- Portada ---
    ruta_index = os.path.join(RAIZ, "index.html")
    if os.path.exists(ruta_index):
        with open(ruta_index, encoding="utf-8") as f:
            plantilla = f.read()
        plantilla_portada = plantilla
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

    # Las paginas nuevas heredan estilo, barra y pie de la portada.
    piezas = piezas_comunes(plantilla_portada)
    dias_hechos = escribir_paginas_de_dia(historial, hoy_iso, piezas)
    extras = [r for r in [escribir_estadisticas(historial, piezas)] if r]
    escribir_sitemap(hoy_iso, dias_hechos, extras)

    print("Listo. Todo en ./publicar/")


if __name__ == "__main__":
    main()
