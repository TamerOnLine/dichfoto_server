(function () {
  function justify(container, defaultRowH = 220, defaultGap = 16) {
    const w = container.clientWidth;
    // ارتفاع الصف حسب العرض
    let rowH = 150;          // موبايل
    if (w >= 768)  rowH = 200;   // تابلت
    if (w >= 1200) rowH = 240;   // ديسكتوب كبير

    // المسافة بين الصور
    let gap = 8;             // موبايل
    if (w >= 768)  gap = 12;     // تابلت
    if (w >= 1200) gap = 16;     // ديسكتوب

    const imgs = Array.from(container.querySelectorAll('img'));
    if (!imgs.length) return;

    let row = [], rowW = 0;

    function flushRow(isLast) {
      const totalGap = gap * (row.length - 1);
      const scale = isLast ? 1 : (w - totalGap) / rowW;
      const rowPx = Math.round(rowH * scale);

      const rowDiv = document.createElement('div');
      rowDiv.style.display = 'flex';
      rowDiv.style.gap = gap + 'px';
      rowDiv.style.marginBottom = gap + 'px';

      row.forEach(({wrap, iw, ih}) => {
        const ratio = iw / ih;
        const itemW = Math.round(rowPx * ratio);
        wrap.style.flex = '0 0 ' + itemW + 'px';
        wrap.style.height = rowPx + 'px';
        const img = wrap.querySelector('img');
        img.style.height = '100%';
        img.style.objectFit = 'cover';
        rowDiv.appendChild(wrap);
      });

      container.appendChild(rowDiv);
    }

    const items = imgs.map(img => {
      const a = img.closest('.jg-item');
      const iw = img.naturalWidth || 800, ih = img.naturalHeight || 600;
      const wrap = document.createElement('div');
      wrap.appendChild(a);
      return {wrap, iw, ih};
    });

    container.classList.add('is-justified');
    container.innerHTML = '';

    for (const it of items) {
      const ratio = it.iw / it.ih;
      const nextW = rowW + rowH * ratio;
      if (nextW + gap * row.length > w && row.length) {
        flushRow(false);
        row = []; rowW = 0;
      }
      row.push(it);
      rowW += rowH * ratio;
    }
    if (row.length) flushRow(true);
  }

  function init() {
    const c = document.getElementById('gallery');
    if (!c) return;
    justify(c);
    window.addEventListener('resize', () => {
      c.innerHTML = '';
      c.classList.remove('is-justified');
      justify(c);
    });
  }
  window.addEventListener('load', init);
})();
