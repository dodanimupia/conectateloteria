# Resultados de Lotería (proyecto de práctica de scraping)

Página estática que muestra resultados de lotería y se actualiza sola
cada 5 minutos, sin depender de tu computadora ni de ningún servidor
que tengas que mantener corriendo.

## Cómo funciona

- `actualizar_datos.py`: consulta Turifamax y, si falla, prueba las portadas
  públicas de `www.loteriasdominicanas.com.do` y `www.conectate.com.do/loterias/`.
  Las fuentes HTML se consultan solo si se puede leer su `robots.txt` y permite
  acceder a la URL. El recopilador se identifica como `ConectateLoteriaBot/1.0`,
  con el enlace de este repositorio. No requiere navegador ni credenciales
  para esas portadas.
- `.github/workflows/actualizar.yml`: le dice a GitHub que ejecute ese
  script automáticamente cada 5 minutos (`cron: "2-59/5 * * * *"`) y que
  guarde los datos y el historial si cambiaron. En los PR ejecuta pruebas;
  la actualización y el envío por FTPS se ejecutan solo desde `main`.
- `index.html`: la landing page / portada del proyecto (explica qué es,
  cómo funciona, y tiene el botón para ir a los resultados).
- `resultados.html`: la página con los datos en vivo. Con `fetch()` lee
  `datos_loteria.json` (mismo dominio, sin problemas de CORS) y pinta
  las tarjetas. Revisa si hay datos nuevos cada 1 minuto.
- `vista-previa.png`: captura usada en la portada para mostrar cómo se
  ve la página de resultados.
- `leidsa_snapshot.html`: referencia antigua; nunca se publica como respaldo.

### Fallos de las fuentes y conservación de datos

Un HTTP 403 significa que el servidor denegó la solicitud; no demuestra por sí
solo si la causa es una restricción de IP, autenticación o protección del sitio.
Los errores 401, 403 y 429 de Turifamax activan la siguiente fuente sin repetir
la petición denegada. No se usan proxies ni técnicas para eludir esos accesos.

Cada fuente debe superar la validación: al menos 20 juegos, cobertura de las
loterías requeridas, números de dos cifras, fechas reales de hasta 31 días y
algún resultado de hoy o ayer. Se rechazan duplicados y fechas inconsistentes.
Se conservan los sorteos recientes ausentes o más nuevos del archivo anterior
y el historial reciente de 14 días al cambiar de fuente. `historial.json` sigue
acumulándose en la construcción de páginas, con su retención de 14 días.
Si todas las fuentes fallan, el proceso termina con error antes de modificar
el JSON, construir páginas o enviar archivos. El reemplazo del JSON es atómico.

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
compartido. La automatización se ejecuta en GitHub Actions con Python y
BeautifulSoup, sin instalar un navegador. La solución: dejar que
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
pip install -r requirements.txt
python3 -m unittest discover -s tests -v
python3 actualizar_datos.py      # genera/actualiza datos_loteria.json
python3 construir_paginas.py     # genera publicar/ y acumula historial.json
python3 -m http.server 8000      # sirve la carpeta localmente
```

Luego abre `http://localhost:8000/index.html` (portada) o
`http://localhost:8000/resultados.html` (datos en vivo directo).

## Aviso

Proyecto educativo, no oficial. Los datos son de referencia; para
jugar o verificar premios, usa siempre las fuentes oficiales de cada
lotería.
