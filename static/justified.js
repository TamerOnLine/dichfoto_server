// Justified layout without fixed columns
(function () {
  const GAP = 10;          // يجب أن يطابق --jg-gap
  const TARGET = 260;      // ارتفاع الصف المستهدف (px) - عدّله لذوقك
  const MAX_PER_ROW = 6;   // حدّ أقصى اختياري لعدد الصور في الصف

  function layout(container) {
    // خذ العناصر دون فقدانها
    const items = Array.from(container.querySelectorAll('.jg-item'));
    if (!items.length) return;

    // جهّز حاوية جديدة للصفوف
    const frag = document.createDocumentFragment();
    let row = [];
    let rowAspect = 0;
    const cw = container.clientWidth;

    function flushRow(finalRow = false) {
      if (!row.length) return;
      // عرض المسافات داخل الصف
      const gaps = GAP * Math.max(0, row.length - 1);
      // احسب ارتفاع الصف بحيث يمتلئ عرض الحاوية بالضبط (مع الحفاظ على النِّسَب)
      let h = (cw - gaps) / rowAspect;        // h = width / sum(ratios)
      // لا نرفع الصف أكثر بكثير من الهدف (شكل أجمل)
      if (!finalRow) h = Math.min(h, TARGET * 1.3);
      // صفّ أخير: نقرّب للهدف بدل تمديد زائد
      if (finalRow && h > TARGET) h = TARGET;

      // أنشئ صفّ
      const rowDiv = document.createElement('div');
      rowDiv.className = 'jg-row';

      row.forEach(({el, ratio}) => {
        const w = h * ratio;                 // العرض الذي يحافظ على النسبة
        el.style.width = w + 'px';           // الارتفاع يتكوّن تلقائيًا
        rowDiv.appendChild(el);
      });
      frag.appendChild(rowDiv);

      // صفّ جديد
      row = [];
      rowAspect = 0;
    }

    items.forEach((el) => {
      const img = el.querySelector('img');
      // fallback لو لم تُحمّل الأبعاد بعد
      const ratio = (img && img.naturalWidth && img.naturalHeight)
        ? img.naturalWidth / img.naturalHeight
        : 1.5;

      row.push({ el, ratio });
      rowAspect += ratio;

      const predictedWidth = rowAspect * TARGET + GAP * Math.max(0, row.length - 1);
      if (predictedWidth >= cw || row.length >= MAX_PER_ROW) {
        flushRow(false);
      }
    });

    // صفّ أخير
    flushRow(true);

    // بدّل محتوى الحاوية بالصفوف
    container.innerHTML = '';
    container.appendChild(frag);
  }

  function debounce(fn, ms){ let t; return () => { clearTimeout(t); t = setTimeout(fn, ms); }; }

  function ready() {
    const container = document.getElementById('gallery');
    if (!container) return;

    const relayout = () => layout(container);

    // انتظر تحميل الصور لتكون ratios دقيقة
    const imgs = container.querySelectorAll('img');
    let pending = imgs.length;
    if (!pending) { relayout(); return; }

    imgs.forEach(img => {
      if (img.complete && img.naturalWidth) {
        if (--pending === 0) relayout();
      } else {
        img.addEventListener('load', () => { if (--pending === 0) relayout(); }, { once: true });
        img.addEventListener('error', () => { if (--pending === 0) relayout(); }, { once: true });
      }
    });

    window.addEventListener('resize', debounce(relayout, 150));
  }

  document.addEventListener('DOMContentLoaded', ready);
})();
