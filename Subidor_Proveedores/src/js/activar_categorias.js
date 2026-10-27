// Activa todas las categorías del formulario de alta de proveedor.
// Es el mismo snippet que se pegaba en la consola (F12), pero devuelve un
// resumen para que Python pueda validar que quedaron todas encendidas.
() => {
  const container = document.querySelector('.custom-dd.dd.nestable_list_1');
  if (!container) return { encontrado: false, total: 0, activadas: 0, apagadas: 0 };
  const todas = Array.from(container.querySelectorAll('input[type="checkbox"]'));
  const offToggles = todas.filter(t => !t.checked);
  let clicked = 0;
  for (const toggle of offToggles) {
    const label = toggle.closest('label') || toggle.nextElementSibling || toggle.parentElement.querySelector('label');
    if (label) label.click();
    else toggle.click();
    clicked++;
  }
  const apagadas = todas.filter(t => !t.checked).length;
  return { encontrado: true, total: todas.length, activadas: clicked, apagadas };
}
