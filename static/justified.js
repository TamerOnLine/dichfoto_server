(function () {
  function justify(container, targetRowH = 220, gap = 8) {
    const imgs = Array.from(container.querySelectorAll('img'));
    if (!imgs.length) return;

    const width = container.clientWidth;
    let row = [], rowW = 0;

    function flushRow(isLast) {
      const totalGap = gap * (row.length - 1);
      const scale = isLast ? 1 : (width - totalGap) / rowW;
      const rowH = Math.round(targetRowH * scale);

      const rowDiv = document.createElement('div');
      rowDiv.style.display = 'flex';
      rowDiv.style.gap = gap + 'px';
      rowDiv.style.marginBottom = gap + 'px';

      row.forEach(({a, w, h}) => {
        const ratio = w / h;
        const itemW = Math.round(rowH * ratio);
        a.style.flex = '0 0 ' + itemW + 'px';
        a.style.height = rowH + 'px';
        const img = a.querySelector('img');
        img.style.height = '100%';
        img.style.objectFit = 'cover';
        rowDiv.appendChild(a);
      });

      container.appendChild(rowDiv);
    }

    const items = imgs.map(img => {
      const a = img.closest('.jg-item');
      const w = +img.dataset.w || img.naturalWidth || 800;
      const h = +img.dataset.h || img.naturalHeight || 600;
      return {a, w, h};
    });

    container.classList.add('is-justified');
    container.innerHTML = '';

    for (const it of items) {
      const ratio = it.w / it.h;
      const nextW = rowW + targetRowH * ratio;
      if (nextW + gap * row.length > width && row.length) {
        flushRow(false);
        row = []; rowW = 0;
      }
      row.push(it);
      rowW += targetRowH * ratio;
    }
    if (row.length) flushRow(true);
  }

  function init() {
    const c = document.getElementById('gallery');
    if (!c) return;
    justify(c);
    let t;
    window.addEventListener('resize', () => {
      clearTimeout(t);
      t = setTimeout(() => { justify(c); }, 150);
    });
  }
  window.addEventListener('load', init);
})();
