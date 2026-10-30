# SEO del sitio generado

Los cambios se aplican en `construir_paginas.py`: cada reconstrucción conserva
los metadatos, canonical, idioma es-DO y datos estructurados WebPage y
BreadcrumbList. Las páginas interiores incluyen una ruta visible a Inicio.
Se conservan los schema WebSite y FAQPage existentes en las plantillas.

Las URLs de portada, operadores, sorteos y fechas no cambian. Los títulos y
descripciones de los sorteos incluyen su operador para distinguir juegos con
el mismo nombre. No se añaden resultados ni fechas de actualización ficticios.

El sitemap omite `lastmod` porque la fecha de un sorteo o de una reconstrucción
no demuestra la última modificación del contenido completo de la página.
Las páginas diarias vacías se excluyen también de los enlaces entre fechas.
Los operadores solo aparecen en el sitemap si se generó su archivo.

Verificación local:

```sh
python -m unittest discover -s tests -v
```

Las pruebas construyen el sitio en una carpeta temporal con datos sintéticos,
comprueban metadatos y JSON-LD, destinos HTML locales, cobertura del sitemap
y conservación del JSON. No consultan resultados en vivo ni publican por FTP.
El flujo de actualización y sus validaciones de frescura permanecen intactos.

Referencias: [sitemaps de Google](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)
y [BreadcrumbList](https://developers.google.com/search/docs/appearance/structured-data/breadcrumb).
La validación externa en Search Console queda pendiente tras la publicación.
