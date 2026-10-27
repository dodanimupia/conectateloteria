(() => {
  'use strict';
  const fuente = document.getElementById('detalle-datos');
  if (!fuente) return;
  const datos = JSON.parse(fuente.textContent);
  const enlaces = [...document.querySelectorAll('[data-fecha]')];
  const ultima = Object.keys(datos).sort().at(-1);
  function mostrar(fecha) {
    if (!datos[fecha]) fecha = ultima;
    const item = datos[fecha];
    if (!item) return;
    const tiempo = document.getElementById('detalle-fecha');
    tiempo.textContent = item.fecha;
    tiempo.dateTime = fecha;
    document.getElementById('detalle-etiqueta').textContent = fecha === ultima ? 'Último resultado disponible' : 'Resultado de la fecha seleccionada';
    const numeros = document.getElementById('detalle-numeros');
    numeros.replaceChildren(...item.numeros.map(n => {
      const bola = document.createElement('span');
      bola.className = 'detalle-bola';
      bola.textContent = n;
      return bola;
    }));
    enlaces.forEach(enlace => {
      if (enlace.dataset.fecha === fecha) enlace.setAttribute('aria-current', 'date');
      else enlace.removeAttribute('aria-current');
    });
  }
  mostrar(new URLSearchParams(location.search).get('fecha'));
  enlaces.forEach(enlace => enlace.addEventListener('click', e => {
    if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    history.pushState(null, '', enlace.href);
    mostrar(enlace.dataset.fecha);
    document.getElementById('resultado-destacado').focus();
  }));
  addEventListener('popstate', () => mostrar(new URLSearchParams(location.search).get('fecha')));
})();
