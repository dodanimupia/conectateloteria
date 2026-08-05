# Resultados de Lotería (proyecto de práctica de scraping)

Página estática que muestra resultados de lotería y se actualiza sola
cada 5 minutos, sin depender de tu computadora ni de ningún servidor
que tengas que mantener corriendo.

## Cómo funciona

- `actualizar_datos.py`: scraper (Playwright + BeautifulSoup) que visita
  `loterias.conectate.com.do`, renderiza el JavaScript de la página,
  extrae juego/fecha/números y guarda todo en `datos_loteria.json`.
- `.github/workflows/actualizar.yml`: le dice a GitHub que ejecute ese
  script automáticamente cada 5 minutos (`cron: "*/5 * * * *"`) y que
  suba (`git commit` + `push`) el `datos_loteria.json` si cambió.
- `index.html`: la landing page / portada del proyecto (explica qué es,
  cómo funciona, y tiene el botón para ir a los resultados).
- `resultados.html`: la página con los datos en vivo. Con `fetch()` lee
  `datos_loteria.json` (mismo dominio, sin problemas de CORS) y pinta
  las tarjetas. Revisa si hay datos nuevos cada 1 minuto.
- `vista-previa.png`: captura usada en la portada para mostrar cómo se
  ve la página de resultados.
- `leidsa_snapshot.html`: respaldo local por si un intento de scraping
  falla (para que `datos_loteria.json` nunca quede vacío).

## Publicarlo en un dominio real (GitHub Pages, gratis)

1. Crea una cuenta en [github.com](https://github.com) si no tienes.
2. Crea un repositorio nuevo (puede ser público o privado) y sube
   TODOS los archivos de esta carpeta manteniendo la estructura
   (incluyendo la carpeta `.github/workflows/`).
3. En el repositorio, ve a **Settings → Actions → General → Workflow
   permissions** y marca **"Read and write permissions"**. Guarda.
   (Sin esto, la Action no podrá hacer commit del JSON actualizado.)
4. Ve a **Settings → Pages**. En "Build and deployment", selecciona
   **Deploy from a branch**, elige la rama `main` y la carpeta `/root`.
   Guarda.
5. Espera uno o dos minutos y GitHub te dará una URL tipo
   `https://tu-usuario.github.io/tu-repositorio/` — esa ya es tu
   página pública, en un dominio real.
6. Ve a la pestaña **Actions** del repositorio: ahí puedes ver el
   workflow "Actualizar resultados de lotería" corriendo, y lanzarlo
   a mano con el botón **"Run workflow"** para no esperar los 5 minutos
   la primera vez.

### ¿Se puede usar mi propio dominio (no el de github.io)?

Sí. En **Settings → Pages → Custom domain** puedes escribir tu dominio
propio (por ejemplo `resultados.midominio.com`) y seguir las
instrucciones de GitHub para apuntar el DNS. GitHub Pages es gratis;
lo único que pagarías es el dominio en sí si quieres uno personalizado.

## Ya está publicado en conectateloteria.com (SiteGround) — falta conectar la automatización

El sitio ya está subido a mano en SiteGround, pero SiteGround es hosting
compartido y no puede correr el scraper (necesita un navegador headless
que ese tipo de hosting no permite instalar). La solución: dejar que
GitHub Actions siga corriendo el scraper cada 5 minutos (gratis) y que,
justo después, empuje el `datos_loteria.json` nuevo a SiteGround por FTP.

Pasos (los tienes que hacer tú, por seguridad de tu cuenta):

1. Sube este proyecto a un repositorio de GitHub (ver sección de arriba,
   pasos 1-3, sin necesidad de activar GitHub Pages esta vez).
2. En SiteGround: **Site Tools → Sitio web → Cuentas FTP → Crear cuenta
   nueva FTP**. Ponle un nombre (ej. `deploy`), dale a **Generar** para
   la contraseña, y copia esa contraseña en un lugar seguro. Click
   **Crear**.
3. En tu repositorio de GitHub: **Settings → Secrets and variables →
   Actions → New repository secret**. Crea dos secrets:
   - `FTP_USERNAME` → el usuario completo que te dio SiteGround
     (algo como `deploy@conectateloteria.com`)
   - `FTP_PASSWORD` → la contraseña que generaste en el paso 2
4. Listo. La próxima vez que corra el workflow (cada 5 min, o dale
   **Run workflow** a mano en la pestaña Actions), va a: scrapear →
   guardar `datos_loteria.json` en GitHub → subir ese mismo archivo a
   `conectateloteria.com/public_html/datos_loteria.json` por FTP.
5. `resultados.html`, ya publicada en SiteGround, va a leer ese archivo
   apenas se actualice (revisa cada 1 minuto) — sin que tengas que subir
   nada a mano nunca más.

Nota: el host FTP es `ftp.conectateloteria.com`, puerto 21, ya
configurado en el workflow — no hace falta que lo agregues tú.

### Nota sobre el cron de GitHub Actions

GitHub permite programar tareas cada 5 minutos como mínimo, pero en
repositorios gratuitos o con mucha carga en GitHub, a veces el
disparo real se atrasa unos minutos — es una limitación de su
infraestructura compartida, no de este proyecto. Para una tarea
escolar es más que suficiente.

## Correrlo en tu computadora (opcional, para probar antes de subirlo)

```bash
pip install playwright beautifulsoup4
playwright install chromium
python3 actualizar_datos.py      # genera/actualiza datos_loteria.json
python3 -m http.server 8000      # sirve la carpeta localmente
```

Luego abre `http://localhost:8000/index.html` (portada) o
`http://localhost:8000/resultados.html` (datos en vivo directo).

## Aviso

Proyecto educativo, no oficial. Los datos son de referencia; para
jugar o verificar premios, usa siempre las fuentes oficiales de cada
lotería.
