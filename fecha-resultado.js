function fechaResultado(item) {
  const partes = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Santo_Domingo', year: 'numeric', month: '2-digit', day: '2-digit'
  }).formatToParts(new Date());
  const valor = tipo => partes.find(parte => parte.type === tipo).value;
  const hoy = `${valor('year')}-${valor('month')}-${valor('day')}`;
  const fecha = item.fecha_iso;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(fecha || '')) return 'Fecha sin confirmar';
  const legible = `${fecha.slice(8, 10)}/${fecha.slice(5, 7)}/${fecha.slice(0, 4)}`;
  return fecha === hoy ? `Hoy · ${legible}` : `Anterior · ${legible}`;
}
