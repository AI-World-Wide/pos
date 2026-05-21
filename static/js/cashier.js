/* Cashier POS — minimal JS helpers for HTMX-driven UI */

// Auto-scroll order lines to bottom when updated
document.body.addEventListener('htmx:afterSwap', function(evt) {
  if (evt.detail.target.id === 'order-panel') {
    var lines = document.getElementById('order-lines');
    if (lines) lines.scrollTop = lines.scrollHeight;
  }
});
