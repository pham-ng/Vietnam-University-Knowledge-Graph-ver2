/* VN-Edu LOD — tiện ích dùng chung: chủ đề sáng/tối, tooltip, biểu đồ SVG nhẹ (không phụ thuộc thư viện) */
(function () {
  const store = { get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
                  set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} } };
  const saved = store.get("vnedu-theme");
  if (saved) document.documentElement.setAttribute("data-theme", saved);
  document.addEventListener("DOMContentLoaded", () => {
    const btn = document.querySelector(".theme-btn");
    if (btn) btn.addEventListener("click", () => {
      const cur = document.documentElement.getAttribute("data-theme")
        || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      const next = cur === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      store.set("vnedu-theme", next);
      document.dispatchEvent(new CustomEvent("themechange"));
    });
  });
})();

const VN = {
  /** Chuẩn hoá chuỗi tiếng Việt để tìm kiếm không dấu. */
  norm(s) { return (s || "").toString().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase(); },
  fmt(n) { return (n ?? 0).toLocaleString("vi-VN"); },
  css(v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); },
  esc(s) { return (s ?? "").toString().replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); },

  tip: null,
  showTip(ev, html) {
    if (!VN.tip) { VN.tip = document.createElement("div"); VN.tip.className = "tip"; document.body.appendChild(VN.tip); }
    VN.tip.innerHTML = html; VN.tip.style.display = "block";
    const w = VN.tip.offsetWidth, h = VN.tip.offsetHeight;
    let x = ev.clientX + 14, y = ev.clientY + 14;
    if (x + w > innerWidth - 8) x = ev.clientX - w - 14;
    if (y + h > innerHeight - 8) y = ev.clientY - h - 14;
    VN.tip.style.left = x + "px"; VN.tip.style.top = y + "px";
  },
  hideTip() { if (VN.tip) VN.tip.style.display = "none"; },

  svg(tag, attrs, parent) {
    const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const k in attrs) el.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(el);
    return el;
  },

  /** Bảng xem dữ liệu (thay thế cho biểu đồ — khả năng tiếp cận). */
  tableView(host, headers, rows) {
    const d = document.createElement("details"); d.className = "tv";
    d.innerHTML = `<summary>Xem dạng bảng</summary><div class="table-wrap"><table><tr>${headers.map((h, i) =>
      `<th class="${i ? "num" : ""}">${VN.esc(h)}</th>`).join("")}</tr>${rows.map(r => `<tr>${r.map((c, i) =>
      `<td class="${i ? "num" : ""}">${typeof c === "number" ? VN.fmt(c) : VN.esc(c)}</td>`).join("")}</tr>`).join("")}</table></div>`;
    host.appendChild(d);
  },

  /**
   * Biểu đồ thanh ngang. series: [{key, label, color}] ; rows: [{label, values:{key:n}, href?}]
   * Một series -> không chú giải; ≥2 series -> thanh xếp chồng có chú giải + nhãn tổng ở cuối.
   */
  hbar(host, rows, series, opts = {}) {
    host.innerHTML = "";
    const multi = series.length > 1;
    if (multi) {
      const lg = document.createElement("div"); lg.className = "legend";
      lg.innerHTML = series.map(s => `<span><i style="background:${VN.css(s.color)}"></i>${VN.esc(s.label)}</span>`).join("");
      host.appendChild(lg);
    }
    const W = 640, labelW = opts.labelW || 210, barH = 16, gap = 10, padR = 56;
    const H = rows.length * (barH + gap) + 6;
    const max = Math.max(1, ...rows.map(r => series.reduce((a, s) => a + (r.values[s.key] || 0), 0)));
    const sc = v => (W - labelW - padR) * v / max;
    const div = document.createElement("div"); div.className = "chart"; host.appendChild(div);
    const svg = VN.svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": opts.title || "biểu đồ" }, div);
    VN.svg("line", { x1: labelW, x2: labelW, y1: 0, y2: H - 4, class: "axis" }, svg);
    rows.forEach((r, i) => {
      const y = i * (barH + gap) + 3;
      const t = VN.svg("text", { x: labelW - 8, y: y + barH - 4, "text-anchor": "end", class: "lbl" }, svg);
      const lab = r.label.length > 30 ? r.label.slice(0, 29) + "…" : r.label;
      if (r.href) { const a = VN.svg("a", { href: r.href }, svg); a.appendChild(t); }
      t.textContent = lab;
      let x = labelW, total = 0;
      series.forEach((s, si) => {
        const v = r.values[s.key] || 0; if (!v) return;
        const w = Math.max(sc(v) - (multi ? 2 : 0), 1.5);
        const last = series.slice(si + 1).every(s2 => !(r.values[s2.key]));
        const rect = VN.svg("path", { d: VN.barPath(x, y, w, barH, last ? 4 : 0), fill: VN.css(s.color) }, svg);
        rect.style.cursor = "default";
        rect.addEventListener("mousemove", e => VN.showTip(e, `<b>${VN.esc(r.label)}</b>${multi ? VN.esc(s.label) + ": " : ""}${VN.fmt(v)}${opts.unit || ""}`));
        rect.addEventListener("mouseleave", VN.hideTip);
        x += sc(v); total += v;
      });
      VN.svg("text", { x: x + 6, y: y + barH - 4, class: "val" }, svg).textContent = VN.fmt(total) + (opts.unit || "");
    });
    VN.tableView(host, ["", ...series.map(s => s.label)], rows.map(r => [r.label, ...series.map(s => r.values[s.key] || 0)]));
  },

  /** Biểu đồ cột dọc một series (VD: theo thập kỷ). */
  vbar(host, rows, color, opts = {}) {
    host.innerHTML = "";
    const W = 640, H = 230, padL = 34, padB = 26, padT = 14;
    const n = rows.length, bw = (W - padL) / n;
    const max = Math.max(1, ...rows.map(r => r.value));
    const nice = Math.ceil(max / 10) * 10;
    const sy = v => (H - padB - padT) * v / nice;
    const div = document.createElement("div"); div.className = "chart"; host.appendChild(div);
    const svg = VN.svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": opts.title || "biểu đồ" }, div);
    const g = VN.svg("g", { class: "grid" }, svg);
    for (let k = 0; k <= 4; k++) {
      const v = nice * k / 4, y = H - padB - sy(v);
      VN.svg("line", { x1: padL, x2: W, y1: y, y2: y }, g);
      VN.svg("text", { x: padL - 6, y: y + 4, "text-anchor": "end", class: "lbl" }, svg).textContent = Math.round(v);
    }
    rows.forEach((r, i) => {
      const x = padL + i * bw + 2, h = sy(r.value), w = Math.max(bw - 4, 2);
      if (r.value) {
        const p = VN.svg("path", { d: VN.colPath(x, H - padB - h, w, h, 4), fill: VN.css(color) }, svg);
        p.addEventListener("mousemove", e => VN.showTip(e, `<b>${VN.esc(r.label)}</b>${VN.fmt(r.value)} cơ sở`));
        p.addEventListener("mouseleave", VN.hideTip);
      }
      if (i % (opts.every || 1) === 0)
        VN.svg("text", { x: x + w / 2, y: H - 8, "text-anchor": "middle", class: "lbl" }, svg).textContent = r.short || r.label;
    });
    VN.svg("line", { x1: padL, x2: W, y1: H - padB, y2: H - padB, class: "axis" }, svg);
    VN.tableView(host, ["", "Số cơ sở"], rows.map(r => [r.label, r.value]));
  },

  barPath(x, y, w, h, r) {   // thanh ngang: chỉ bo 2 góc ở đầu dữ liệu (bên phải)
    r = Math.min(r, w / 2, h / 2);
    return `M${x},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h - r} Q${x + w},${y + h} ${x + w - r},${y + h} H${x} Z`;
  },
  colPath(x, y, w, h, r) {   // cột dọc: bo 2 góc phía trên
    r = Math.min(r, w / 2, h);
    return `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h} Z`;
  },
};
