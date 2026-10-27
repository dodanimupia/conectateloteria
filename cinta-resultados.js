(() => {
  "use strict";
  const cinta = document.getElementById("cinta-resultados");
  if (!cinta) return;
  const pista = cinta.querySelector(".cinta-pista");
  const boton = cinta.querySelector(".cinta-pausa");
  let firmaAnterior = "";

  function ajustarVelocidad() {
    const grupo = pista.querySelector(".cinta-grupo");
    if (grupo) pista.style.setProperty("--cinta-duracion", Math.max(30, grupo.scrollWidth / 65) + "s");
  }

  boton.addEventListener("click", () => {
    const pausada = cinta.dataset.pausada !== "true";
    cinta.dataset.pausada = String(pausada);
    boton.setAttribute("aria-pressed", String(pausada));
    boton.setAttribute("aria-label", pausada ? "Reanudar resultados en movimiento" : "Pausar resultados en movimiento");
    boton.title = pausada ? "Reanudar" : "Pausar";
    boton.textContent = pausada ? "▶" : "Ⅱ";
  });

  function pintar(lista) {
    const partes = new Intl.DateTimeFormat("es-DO", {
      timeZone: "America/Santo_Domingo", day: "2-digit", month: "2-digit"
    }).formatToParts(new Date());
    const hoy = partes.find(p => p.type === "day").value + "-" + partes.find(p => p.type === "month").value;
    const validos = lista.filter(item => item.juego && Array.isArray(item.numeros) && item.numeros.length);
    if (!validos.length) return;
    const firma = hoy + JSON.stringify(validos.map(item => [item.empresa, item.juego, item.fecha, item.numeros]));
    // Una consulta sin cambios no reinicia el recorrido de la franja.
    if (firma === firmaAnterior) return;
    firmaAnterior = firma;
    const nombres = new Map();
    for (const item of validos) nombres.set(item.juego, (nombres.get(item.juego) || 0) + 1);
    const grupo = document.createElement("div");
    grupo.className = "cinta-grupo";
    grupo.setAttribute("role", "list");
    for (const item of validos) {
      const entrada = document.createElement("div");
      entrada.className = "cinta-item";
      entrada.setAttribute("role", "listitem");
      const nombre = document.createElement("span");
      nombre.className = "cinta-nombre";
      nombre.textContent = item.juego + (nombres.get(item.juego) > 1 ? " · " + (item.empresa || "") : "");
      const numeros = document.createElement("span");
      numeros.className = "cinta-numeros";
      for (const numero of item.numeros) {
        const bola = document.createElement("span");
        bola.className = "cinta-bola";
        bola.textContent = String(numero);
        numeros.appendChild(bola);
      }
      const fecha = document.createElement("span");
      fecha.className = "cinta-fecha" + (item.fecha === hoy ? " cinta-fecha-hoy" : "");
      fecha.textContent = item.fecha === hoy ? "HOY" : (item.fecha || "Sin fecha").replace("-", "/");
      entrada.append(nombre, numeros, fecha);
      grupo.appendChild(entrada);
    }
    const copia = grupo.cloneNode(true);
    copia.setAttribute("aria-hidden", "true");
    pista.replaceChildren(grupo, copia);
    ajustarVelocidad();
  }

  async function actualizar() {
    try {
      const respuesta = await fetch("datos_loteria.json?_cinta=" + Date.now(), { cache: "no-store" });
      if (!respuesta.ok) return;
      const paquete = await respuesta.json();
      if (paquete.en_vivo === true && Array.isArray(paquete.resultados)) pintar(paquete.resultados);
    } catch (_) {
      // Conserva la franja ya publicada si falla la consulta.
    }
  }

  ajustarVelocidad();
  actualizar();
  setInterval(actualizar, 60000);
  window.addEventListener("resize", ajustarVelocidad);
})();
