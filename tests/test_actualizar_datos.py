import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import actualizar_datos as datos
import historial


AHORA = dt.datetime.now(datos.ZONA)


def resultados_validos():
    return [
        {"empresa": empresa, "juego": f"Juego {numero}",
         "fecha": AHORA.strftime("%d-%m"), "fecha_iso": AHORA.date().isoformat(),
         "numeros": ["00", "12", "99"]}
        for empresa in datos.EMPRESAS.values() for numero in range(2)
    ]


class ActualizacionTests(unittest.TestCase):
    def test_403_no_se_reintenta_y_activa_alternativa(self):
        error = HTTPError(datos.URL_API, 403, "Forbidden", {}, None)
        with patch.object(datos, "urlopen", side_effect=error) as abrir:
            with patch.object(datos, "obtener_html_publico", return_value="html") as publico:
                with patch.object(datos, "extraer_resultados", return_value=resultados_validos()):
                    self.assertEqual(datos.obtener_html_renderizado(), ("html", True))
        self.assertEqual(abrir.call_count, 1)
        publico.assert_called_once_with(datos.URL_ALTERNATIVA)

    def test_401_y_429_no_se_reintentan(self):
        for codigo in (401, 429):
            with self.subTest(codigo=codigo):
                error = HTTPError(datos.URL_API, codigo, "Denied", {}, None)
                with patch.object(datos, "urlopen", side_effect=error) as abrir:
                    with self.assertRaises(RuntimeError):
                        datos.obtener_api()
                self.assertEqual(abrir.call_count, 1)

    def test_alternativa_incompleta_pasa_a_siguiente_fuente(self):
        with patch.object(datos, "obtener_api", side_effect=RuntimeError("403")):
            with patch.object(datos, "obtener_html_publico", side_effect=["parcial", "completa"]) as abrir:
                with patch.object(datos, "extraer_resultados", side_effect=[[], resultados_validos()]):
                    self.assertEqual(datos.obtener_html_renderizado(), ("completa", True))
        self.assertEqual(abrir.call_count, 2)

    def test_robots_denegado_impide_consultar_portada(self):
        class Respuesta:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b"User-agent: ConectateLoteriaBot\nDisallow: /\n"

        with patch.object(datos, "urlopen", return_value=Respuesta()) as abrir:
            with self.assertRaises(ValueError):
                datos.obtener_html_publico(datos.URL_ALTERNATIVA)
        self.assertEqual(abrir.call_count, 1)
        self.assertEqual(abrir.call_args.args[0].get_header("User-agent"), datos.AGENTE)

    def test_rechaza_numeros_fechas_y_duplicados(self):
        for cambio in ({"numeros": ["1", "02", "03"]},
                       {"fecha_iso": (AHORA.date() + dt.timedelta(days=1)).isoformat()},
                       {"fecha": "01-01", "fecha_iso": "2020-01-01"}):
            with self.subTest(cambio=cambio):
                resultados = resultados_validos()
                resultados[0].update(cambio)
                with self.assertRaises(ValueError):
                    datos.validar_resultados(resultados, AHORA)
        resultados = resultados_validos()
        resultados.append(resultados[0])
        with self.assertRaises(ValueError):
            datos.validar_resultados(resultados, AHORA)

    def test_fallo_total_conserva_archivos(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "datos_loteria.json"
            ruta.write_text('{"previo": true}')
            historico = Path(temporal) / "historial.json"
            historico.write_text('{"dias": {"2026-10-27": []}}')
            with patch.object(datos, "ARCHIVO_DATOS", str(ruta)):
                with patch.object(datos, "obtener_api", side_effect=RuntimeError("403")):
                    with patch.object(datos, "obtener_html_publico", side_effect=OSError("sin acceso")):
                        with self.assertRaises(RuntimeError):
                            datos.actualizar_archivo_datos()
            self.assertEqual(ruta.read_text(), '{"previo": true}')
            self.assertEqual(historico.read_text(), '{"dias": {"2026-10-27": []}}')
            self.assertFalse(ruta.with_suffix(".json.tmp").exists())

    def test_cambio_de_fuente_conserva_historial_y_sorteo_mas_nuevo(self):
        resultados = resultados_validos()
        ayer = AHORA.date() - dt.timedelta(days=1)
        antiguo = dict(resultados[0], fecha=ayer.strftime("%d-%m"), fecha_iso=ayer.isoformat())
        guardado = dict(resultados[0], numeros=["11", "22", "33"], fuente=datos.URL_API)
        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "datos_loteria.json"
            ruta.write_text(json.dumps({"en_vivo": True, "fuente": datos.URL_API,
                                        "resultados": [guardado], "historial_reciente": [antiguo]}))
            with patch.object(datos, "ARCHIVO_DATOS", str(ruta)):
                with patch.object(datos, "obtener_html_renderizado", return_value=("data-resultados-esperados", True)):
                    with patch.object(datos, "extraer_resultados", return_value=[antiguo] + resultados[1:]):
                        paquete = datos.actualizar_archivo_datos()
            self.assertEqual(paquete["fuente"], datos.URL_ALTERNATIVA)
            self.assertEqual(paquete["resultados"][0]["numeros"], guardado["numeros"])
            self.assertIn(ayer.isoformat(), {item["fecha_iso"] for item in paquete["historial_reciente"]})
            previo = {"dias": {ayer.isoformat(): [{"empresa": "Otra", "juego": "Anterior", "numeros": ["12"]}]}}
            actualizado = historial.actualizar(previo, paquete["historial_reciente"], AHORA.date())
            self.assertEqual(actualizado["dias"][ayer.isoformat()][0]["juego"], "Anterior")

    def test_parser_alternativo_solo_acepta_tarjetas_completas(self):
        html = '''<section class="lottery-group"><h2>Nacional</h2>
        <article class="draw-item" data-fecha-resultado="2026-10-27"
          data-resultados-esperados="3" data-share-sorteo="Gana Mas">
          <div class="balls"><span class="ball">00</span><span class="ball">12</span>
          <span class="ball">99</span></div></article></section>'''
        self.assertEqual(datos.extraer_resultados(html)[0]["numeros"], ["00", "12", "99"])
        self.assertEqual(datos.extraer_resultados(html.replace('esperados="3"', 'esperados="4"')), [])


if __name__ == "__main__":
    unittest.main()
