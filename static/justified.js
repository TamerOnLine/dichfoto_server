// /static/justified.js
(function () {
  function justify(container, targetRowH = 220, gap = 16) {
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

      row.forEach(({wrap, w, h}) => {
        const ratio = w / h;
        const itemW = Math.round(rowH * ratio);
        wrap.style.flex = '0 0 ' + itemW + 'px';
        wrap.style.height = rowH + 'px';
        wrap.querySelector('img').style.height = '100%';
        wrap.querySelector('img').style.objectFit = 'cover';
        rowDiv.appendChild(wrap);
      });

      container.appendChild(rowDiv);
    }

    // اجمع المقاسات أولاً
    const items = imgs.map(img => {
      const a = img.closest('.jg-item');
      const w = img.naturalWidth || 800, h = img.naturalHeight || 600;
      const wrap = document.createElement('div');
      wrap.appendChild(a);
      return {wrap, w, h};
    });

    container.classList.add('is-justified');
    container.innerHTML = '';

    for (const it of items) {
      const ratio = it.w / it.h;
      const nextW = rowW + targetRowH * ratio;
      if (nextW + gap * row.length > container.clientWidth && row.length) {
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
    window.addEventListener('resize', () => { c.innerHTML=''; c.classList.remove('is-justified'); justify(c); });
  }
  window.addEventListener('load', init);
})();
