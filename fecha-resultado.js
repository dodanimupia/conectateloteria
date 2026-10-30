function fechaResultado(item) {
  const fecha = item.fecha_iso;
  if (/^\d{4}-\d{2}-\d{2}$/.test(fecha || '')) {
    return `${fecha.slice(8, 10)}/${fecha.slice(5, 7)}`;
  }
  return /^\d{2}-\d{2}$/.test(item.fecha || '') ? item.fecha.replace('-', '/') : '';
}
