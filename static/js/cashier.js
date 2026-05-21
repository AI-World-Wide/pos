/* Cashier POS — JS helpers for HTMX-driven UI */

// Auto-scroll order lines to bottom when updated + restart timer
document.body.addEventListener('htmx:afterSwap', function(evt) {
  if (evt.detail.target.id === 'order-panel') {
    var lines = document.getElementById('order-lines');
    if (lines) lines.scrollTop = lines.scrollHeight;
    startOrderTimer();
  }
});

// --- Order panel timer ---
var orderTimerInterval = null;
function startOrderTimer() {
  if (orderTimerInterval) clearInterval(orderTimerInterval);
  var el = document.querySelector('.order-timer');
  if (!el) return;
  var opened = el.getAttribute('data-opened');
  if (!opened) return;
  function tick() {
    var start = new Date(opened);
    var now = new Date();
    var diff = Math.floor((now - start) / 1000);
    if (diff < 0) diff = 0;
    var days = Math.floor(diff / 86400);
    var hours = Math.floor((diff % 86400) / 3600);
    var mins = Math.floor((diff % 3600) / 60);
    var secs = diff % 60;
    var parts = [];
    if (days > 0) parts.push(days + 'd');
    parts.push(
      String(hours).padStart(2, '0') + ':' +
      String(mins).padStart(2, '0') + ':' +
      String(secs).padStart(2, '0')
    );
    el.querySelector('.order-timer__value').textContent = parts.join(' ');
  }
  tick();
  orderTimerInterval = setInterval(tick, 1000);
}
startOrderTimer();
