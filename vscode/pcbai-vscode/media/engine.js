(function () {
  const vscode = acquireVsCodeApi();
  const $ = id => document.getElementById(id);
  for (const id of ['apply', 'cancel']) $(id).addEventListener('click', () => {
    $('apply').disabled = true; $('cancel').disabled = true;
    vscode.postMessage({ type: id });
  });
  window.addEventListener('message', ({ data: m }) => {
    if (m?.type === 'preview') {
      for (const name of ['before', 'after']) {
        $(name).replaceChildren();
        if (m[name].viewbox) $(name).style.aspectRatio = `${m[name].viewbox[2]} / ${m[name].viewbox[3]}`;
        for (const layer of m[name].layers) {
          const image = document.createElement('img'); image.src = layer.uri; image.alt = layer.name;
          $(name).append(image);
        }
      }
      const p = m.preview, metrics = p.engine_metrics;
      const rows = [['Rotalanmamış bağlantı', metrics.unconnected_before, metrics.unconnected_after],
        ['DRC hatası', p.drc_before.errors, p.drc_after.errors], ['Via', metrics.before.via_count, metrics.after.via_count],
        ['İz uzunluğu (mm)', metrics.before.length_mm, metrics.after.length_mm], ['Taşınan parça', 0, metrics.moved_count]];
      $('metrics').replaceChildren();
      for (const row of rows) {
        const tr = document.createElement('tr');
        for (const value of row) { const td = document.createElement('td'); td.textContent = String(value); tr.append(td); }
        $('metrics').append(tr);
      }
      $('status').textContent = p.summary;
      $('evidence').textContent = `Kanıt: ${p.preview_evidence_id} · süre ${p.engine_run.seconds} sn`;
      $('blockers').textContent = (p.blockers || []).join(', ');
      for (const marker of p.diagnostic_markers || []) {
        const [x, y] = marker.points_mm[0];
        const [a, b, c, d, e, f] = m.after.mm_to_svg;
        const [minX, minY, width, height] = m.after.viewbox;
        const dot = document.createElement('span'); dot.className = 'diagnostic'; dot.textContent = '!'; dot.title = marker.note;
        dot.style.left = `${100 * (a * x + c * y + e - minX) / width}%`;
        dot.style.top = `${100 * (b * x + d * y + f - minY) / height}%`;
        $('after').append(dot);
      }
      $('apply').disabled = !!p.blockers?.length; $('cancel').disabled = false;
    } else if (m?.type === 'applied') {
      $('status').textContent = m.summary;
      $('evidence').textContent = `Kontrol noktası: ${m.checkpoint} · kanıt: ${m.evidence}`;
      $('apply').disabled = true; $('cancel').disabled = true;
    } else if (m?.type === 'error') {
      $('error').textContent = m.message; $('cancel').disabled = false;
    }
  });
  vscode.postMessage({ type: 'ready' });
}());
