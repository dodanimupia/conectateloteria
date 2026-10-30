import contextlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

import construir_paginas as paginas
from test_actualizar_datos import AHORA, resultados_validos


class ConstruccionTests(unittest.TestCase):
    def test_fechas_distinguen_resultados_anteriores(self):
        item = {"empresa": "Leidsa", "juego": "Quiniela", "numeros": ["01"],
                "fecha_iso": "2020-01-02"}
        self.assertIn("Anterior · 02/01/2020", paginas.tarjeta(item))
        item["fecha_iso"] = AHORA.date().isoformat()
        self.assertIn("Hoy ·", paginas.tarjeta(item))
        item["fecha_iso"] = ""
        self.assertIn("Fecha sin confirmar", paginas.tarjeta(item))

    def test_acceso_ayer_solo_si_hay_datos(self):
        from datetime import timedelta
        ayer = (AHORA.date() - timedelta(days=1)).isoformat()
        self.assertNotIn("Resultados de ayer", paginas.accesos_fechas({"dias": {}}, AHORA.date()))
        enlaces = paginas.accesos_fechas({"dias": {ayer: [{}]}}, AHORA.date())
        self.assertIn(paginas.ruta_dia(ayer), enlaces)

    def test_construccion_completa_preserva_datos_y_urls(self):
        with tempfile.TemporaryDirectory() as carpeta:
            raiz = Path(carpeta)
            for origen in Path(paginas.RAIZ).iterdir():
                if origen.is_file():
                    shutil.copy(origen, raiz / origen.name)
            paquete = {"en_vivo": True, "actualizado": AHORA.isoformat(),
                       "resultados": resultados_validos()}
            (raiz / "datos_loteria.json").write_text(json.dumps(paquete))
            (raiz / "historial.json").write_text('{"dias": {}}')
            salida = raiz / "publicar"
            with patch.multiple(paginas, RAIZ=str(raiz), SALIDA=str(salida),
                                JSON_DATOS=str(raiz / "datos_loteria.json"),
                                JSON_HISTORIAL=str(raiz / "historial.json")):
                with contextlib.redirect_stdout(io.StringIO()):
                    paginas.main()
            self.assertEqual(json.loads((salida / "datos_loteria.json").read_text()), paquete)
            urls = []
            for archivo in salida.glob("*.html"):
                soup = BeautifulSoup(archivo.read_text(), "html.parser")
                self.assertEqual(soup.html["lang"], "es-DO")
                self.assertIsNotNone(soup.select_one('script[src="fecha-resultado.js?v=1"]'))
                self.assertNotIn("<!--ACCESOS", str(soup))
                canonical = soup.select('link[rel="canonical"]')
                self.assertEqual(len(canonical), 1)
                ruta = "" if archivo.name == "index.html" else archivo.name
                self.assertEqual(canonical[0]["href"], paginas.DOMINIO + ruta)
                urls.append(canonical[0]["href"])
                self.assertEqual(soup.select_one('meta[property="og:title"]')["content"], soup.title.string)
                schemas = [json.loads(script.string) for script in soup.select('script[type="application/ld+json"]')]
                self.assertTrue(any(schema.get("@type") == "WebPage" for schema in schemas))
                if ruta:
                    self.assertTrue(any(schema.get("@type") == "BreadcrumbList" for schema in schemas))
                for enlace in soup.select('a[href]'):
                    destino = enlace["href"].split("?")[0].split("#")[0]
                    if destino.endswith(".html") and ":" not in destino:
                        self.assertTrue((salida / destino).exists(), destino)
            sitemap = ET.parse(salida / "sitemap.xml")
            ubicaciones = [elemento.text for elemento in sitemap.findall('.//{*}loc')]
            self.assertEqual(set(ubicaciones), set(urls))
            self.assertEqual(len(ubicaciones), len(set(ubicaciones)))
            for item in paquete["resultados"]:
                self.assertTrue((salida / paginas.ruta_sorteo(item["empresa"], item["juego"])).exists())

    def test_metadatos_escapan_texto_y_script(self):
        plantilla = '<html lang="es"><head><title>A &amp; B</title><meta name="description" content="&lt;/script&gt;"></head><body></body></html>'
        soup = BeautifulSoup(paginas.completar_seo("prueba.html", plantilla), "html.parser")
        schema = json.loads(soup.select_one('script[type="application/ld+json"]').string)
        self.assertEqual(schema["description"], "</script>")
        self.assertEqual(schema["name"], "A & B")
