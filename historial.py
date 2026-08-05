# -*- coding: utf-8 -*-
"""
Guarda el historial de los últimos días de sorteos.

Por qué existe
--------------
La fuente solo publica los resultados del momento: no hay forma de pedirle
"los números del martes pasado". Así que el historial se construye
acumulando: cada vez que corre el proceso, este módulo toma los resultados
del día y los va guardando en historial.json, que se conserva en el
repositorio de una ejecución a la siguiente.

Eso significa que el historial empieza vacío y se llena solo con el tiempo:
al primer día habrá un día, a la semana habrá siete. No se puede rellenar
hacia atrás.

Formato de historial.json:
{
  "dias": {
    "2026-08-05": [ {"empresa": ..., "juego": ..., "numeros": [...]}, ... ],
    "2026-08-04": [ ... ]
  }
}
"""

import json
import os
from datetime import date, timedelta

DIAS_A_GUARDAR = 8          # 7 días de historial + el día en curso
DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves",
               "viernes", "sábado", "domingo"]
MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun",
                "jul", "ago", "sep", "oct", "nov", "dic"]


def fecha_completa(ddmm, hoy):
    """
    Convierte el "05-08" que trae la fuente en una fecha real (2026-08-05).

    Como la fuente no incluye el año, se asume el año en curso. Si eso diera
    una fecha en el futuro (pasa a fin de año, cuando aún se ven sorteos de
    diciembre en enero), se toma el año anterior.
    """
    if not ddmm or len(str(ddmm)) < 5:
        return None
    try:
        dia = int(str(ddmm)[0:2])
        mes = int(str(ddmm)[3:5])
        candidata = date(hoy.year, mes, dia)
    except ValueError:
        return None
    if candidata > hoy + timedelta(days=2):
        try:
            candidata = date(hoy.year - 1, mes, dia)
        except ValueError:
            return None
    return candidata


def cargar(ruta):
    """Lee historial.json. Si no existe todavía, devuelve uno vacío."""
    if not os.path.exists(ruta):
        return {"dias": {}}
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        if "dias" not in datos:
            datos = {"dias": {}}
        return datos
    except (ValueError, OSError):
        # Si el archivo se corrompió, es preferible empezar de cero
        # antes que romper la construcción de las páginas.
        return {"dias": {}}


def actualizar(historial, resultados, hoy):
    """
    Mete los resultados de esta pasada en el historial y descarta lo viejo.

    Cada sorteo se identifica por (empresa, juego, fecha). Si ya estaba
    guardado, se sobrescribe con la versión nueva: así, si la fuente corrige
    un número, el historial se corrige también.
    """
    dias = historial.setdefault("dias", {})

    for item in resultados:
        f = fecha_completa(item.get("fecha"), hoy)
        if f is None:
            continue  # sorteos sin fecha no entran al historial
        clave = f.isoformat()
        delDia = dias.setdefault(clave, [])

        nuevo = {
            "empresa": item.get("empresa", ""),
            "juego": item.get("juego", ""),
            "numeros": item.get("numeros", []),
        }
        for i, guardado in enumerate(delDia):
            if (guardado.get("empresa") == nuevo["empresa"]
                    and guardado.get("juego") == nuevo["juego"]):
                delDia[i] = nuevo
                break
        else:
            delDia.append(nuevo)

    # Deja solo los días más recientes
    limite = hoy - timedelta(days=DIAS_A_GUARDAR - 1)
    for clave in list(dias.keys()):
        try:
            if date.fromisoformat(clave) < limite:
                del dias[clave]
        except ValueError:
            del dias[clave]

    return historial


def guardar(historial, ruta):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=1)


def fecha_bonita(iso):
    """'2026-08-04' -> 'martes 4 ago'"""
    f = date.fromisoformat(iso)
    return "%s %d %s" % (DIAS_SEMANA[f.weekday()], f.day, MESES_CORTOS[f.month - 1])


def dias_ordenados(historial, excluir=None):
    """Fechas de más reciente a más antigua, sin incluir la de hoy."""
    claves = sorted(historial.get("dias", {}).keys(), reverse=True)
    if excluir:
        claves = [c for c in claves if c != excluir]
    return claves


def por_juego(historial, empresa, hoy_iso):
    """
    Reorganiza el historial de una lotería: para cada juego, la lista de
    días con sus números. Devuelve [(juego, [(fechaISO, numeros), ...]), ...]
    """
    juegos = {}
    for clave in dias_ordenados(historial, excluir=hoy_iso):
        for item in historial["dias"][clave]:
            if item.get("empresa") != empresa:
                continue
            juegos.setdefault(item.get("juego", ""), []).append(
                (clave, item.get("numeros", [])))
    return sorted(juegos.items())
