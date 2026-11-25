(() => {
  const stack = [];
  const inerted = new Set();
  const focusable = panel => [...panel.querySelectorAll('button, input, select, textarea, a[href], summary, [tabindex]')]
    .filter(node => node.tabIndex >= 0 && !node.matches(':disabled') && node.getClientRects().length);
  const top = () => stack.at(-1);

  function updateInert() {
    for (const node of inerted) node.inert = false;
    inerted.clear();
    const current = top();
    if (!current) return;
    for (const node of document.body.children) {
      if (node !== current.panel && node !== current.backdrop && !node.inert) {
        node.inert = true;
        inerted.add(node);
      }
    }
  }

  function attach(panel) {
    if (panel.showModal) return panel;
    const backdrop = document.createElement('div');
    backdrop.className = 'app-dialog-backdrop';
    let opener, modal;
    const entry = {panel, backdrop};
    const cancel = () => {
      if (panel.dispatchEvent(new Event('cancel', {cancelable:true}))) panel.close();
    };
    entry.cancel = cancel;
    let pressedOutside = false;
    backdrop.addEventListener('pointerdown', event => { pressedOutside = event.button === 0; });
    backdrop.addEventListener('pointercancel', () => { pressedOutside = false; });
    backdrop.addEventListener('click', () => {
      if (pressedOutside && top() === entry) cancel();
      pressedOutside = false;
    });

    Object.defineProperty(panel, 'open', {get: () => panel.hasAttribute('open')});
    panel.tabIndex = -1;
    const open = asModal => {
      if (panel.open) return;
      opener = document.activeElement;
      panel.hidden = false;
      panel.setAttribute('open', '');
      modal = asModal;
      if (modal) {
        document.body.append(backdrop);
        panel.setAttribute('aria-modal', 'true');
        backdrop.style.zIndex = 100 + stack.length * 2;
        panel.style.zIndex = 101 + stack.length * 2;
        stack.push(entry);
        updateInert();
      }
      (panel.querySelector('[autofocus]') || focusable(panel)[0] || panel).focus({preventScroll:true});
    };
    panel.show = () => open(false);
    panel.showModal = () => open(true);
    panel.close = () => {
      if (!panel.open) return;
      const restoreFocus = panel.contains(document.activeElement) || modal;
      panel.hidden = true;
      panel.removeAttribute('open');
      if (modal) {
        stack.splice(stack.indexOf(entry), 1);
        backdrop.remove();
        panel.removeAttribute('aria-modal');
        panel.style.removeProperty('z-index');
        updateInert();
      }
      if (restoreFocus) opener?.focus({preventScroll:true});
      panel.dispatchEvent(new Event('close'));
    };
    return panel;
  }

  document.addEventListener('keydown', event => {
    const current = top();
    if (!current) return;
    if (event.key === 'Escape' && !event.isComposing) {
      event.preventDefault();
      event.stopImmediatePropagation();
      current.cancel();
    } else if (event.key === 'Tab') {
      const nodes = focusable(current.panel);
      const index = nodes.indexOf(document.activeElement);
      if (index === -1 || index === (event.shiftKey ? 0 : nodes.length - 1)) {
        event.preventDefault();
        (nodes[event.shiftKey ? nodes.length - 1 : 0] || current.panel).focus();
      }
    }
  }, true);

  function confirmAction(message, action = 'Continue', cancelLabel = 'Cancel') {
    const panel = document.createElement('div');
    panel.className = 'app-dialog app-confirm';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', message);
    const title = document.createElement('p');
    title.textContent = message;
    const buttons = document.createElement('div');
    const cancel = document.createElement('button');
    cancel.textContent = cancelLabel;
    const accept = document.createElement('button');
    accept.textContent = action;
    buttons.append(cancel, accept);
    panel.append(title, buttons);
    document.body.append(panel);
    attach(panel);
    return new Promise(resolve => {
      let accepted = false;
      cancel.onclick = () => panel.close();
      accept.onclick = () => { accepted = true; panel.close(); };
      panel.addEventListener('close', () => { panel.remove(); resolve(accepted); }, {once:true});
      panel.showModal();
    });
  }

  window.readerDialogs = {attach, confirm:confirmAction};
})();
