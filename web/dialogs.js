// Dismiss only when a press starts and ends on the backdrop. Dragging a text
// selection out of a dialog must not accidentally close it.
for (const dialog of document.querySelectorAll('dialog')) {
  let pressedOutside = false;
  const outside = event => {
    const rect = dialog.getBoundingClientRect();
    return event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right
      || event.clientY < rect.top || event.clientY > rect.bottom);
  };
  dialog.addEventListener('pointerdown', event => {
    pressedOutside = event.button === 0 && outside(event);
  });
  dialog.addEventListener('click', event => {
    if (pressedOutside && outside(event)) dialog.close();
    pressedOutside = false;
  });
  dialog.addEventListener('pointercancel', () => { pressedOutside = false; });
  dialog.addEventListener('close', () => { pressedOutside = false; });
}
