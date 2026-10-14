// Side bar webview: text is rendered with textContent only; marker notes are data.
(function () {
  const vscode = acquireVsCodeApi();
  const $ = id => document.getElementById(id);
  const saved = vscode.getState() || {};
  $('request').value = saved.request || '';
  $('hide-done').checked = !!saved.hideDone;
  const applyHide = () => $('markers').classList.toggle('hide-done', $('hide-done').checked);
  applyHide();
  $('hide-done').addEventListener('change', () => { saved.hideDone = $('hide-done').checked; vscode.setState(saved); applyHide(); });
  $('delete-done').addEventListener('click', () => vscode.postMessage({ type: 'deleteDone' }));
  const action = (text, title, type, n) => {
    const button = document.createElement('button'); button.className = 'icon'; button.textContent = text; button.title = title;
    button.addEventListener('click', () => vscode.postMessage({ type, n })); return button;
  };
  const chosen = () => [...document.querySelectorAll('#markers input:checked')].map(i => Number(i.value));
  const send = type => vscode.postMessage({ type, request: $('request').value, markers: chosen() });
  $('request').addEventListener('input', () => { saved.request = $('request').value; vscode.setState(saved); });
  for (const button of document.querySelectorAll('[data-command]')) {
    button.addEventListener('click', () => vscode.postMessage({ type: 'command', command: button.dataset.command }));
  }
  $('pick').addEventListener('click', () => vscode.postMessage({ type: 'pick' }));
  $('reload').addEventListener('click', () => vscode.postMessage({ type: 'reload' }));
  $('open').addEventListener('click', () => send('open'));
  $('copy').addEventListener('click', () => send('copy'));
  $('agent').addEventListener('change', () => vscode.postMessage({ type: 'agent', id: $('agent').value }));
  window.addEventListener('message', event => {
    const m = event.data;
    if (m?.type === 'state') {
      $('project').textContent = m.project ? m.project.replace(/\.kicad_pro$/, '') : 'Proje seçilmedi';
      $('project').title = m.root || '';
      const list = $('markers'); list.replaceChildren();
      if (!m.markers.length) {
        const p = document.createElement('p'); p.className = 'muted';
        p.textContent = m.project ? 'Bu projede işaret yok. Görünümlerde "İşaret koy" ile ekleyebilirsin.' : 'Proje seçilmedi.';
        list.append(p);
      }
      for (const marker of m.markers) {
        const done = marker.status === 'done';
        const row = document.createElement('div');
        row.className = 'marker' + (marker.open ? '' : ' closed') + (done ? ' done' : '');
        const label = document.createElement('label');
        const box = document.createElement('input'); box.type = 'checkbox'; box.value = marker.n; box.checked = marker.open;
        box.disabled = done; box.title = done ? 'Bitmiş işaret isteme eklenmez' : 'İsteme ekle';
        const text = document.createElement('span'); text.className = 'note';
        text.textContent = marker.text + (marker.open || done ? '' : ' — ' + marker.status);
        label.append(box, text);
        if (done) {
          const tag = document.createElement('span'); tag.className = 'tag';
          tag.textContent = marker.closedBy === 'user' ? '✓ (elle)' : '✓';
          tag.title = marker.closedBy === 'user' ? 'Kullanıcı elle bitti işaretledi' : 'Ajan kanıtıyla bitti: ' + (marker.evidence || '');
          label.append(tag);
        }
        row.append(label,
          action(done ? '↺' : '✓', done ? 'Yeniden aç' : 'Bitti olarak işaretle', 'markerStatus', marker.n),
          action('🗑', 'Sil (onay sorulur, kontrol noktası alınır)', 'markerDelete', marker.n));
        list.append(row);
      }
    } else if (m?.type === 'agents') {
      const select = $('agent'); select.replaceChildren();
      for (const agent of m.items) {
        const option = document.createElement('option');
        option.value = agent.id; option.disabled = !agent.available;
        option.textContent = `${agent.label} — ${agent.available ? agent.detail : 'kurulu değil'}`;
        select.append(option);
      }
      select.value = m.selected;
      $('mcp').textContent = m.mcpMissing || ''; $('mcp').hidden = !m.mcpMissing;
      const chosen = m.items.find(a => a.id === m.selected);
      $('open').textContent = chosen && chosen.id !== 'clipboard' ? `${chosen.label} ile gönder` : 'Panoya kopyala';
    } else if (m?.type === 'events') {
      const list = $('activity');
      for (const event of m.items) {
        const li = document.createElement('li');
        li.textContent = event.text; li.className = event.outcome.startsWith('error') ? 'error' : event.outcome;
        list.append(li);
        if (event.hint) { $('message').textContent = event.hint; $('message').className = event.outcome === 'blocked' ? 'error' : 'muted'; }
      }
      while (list.children.length > 50) list.firstChild.remove();
    } else if (m?.type === 'request') {
      $('request').value = m.text; saved.request = m.text; vscode.setState(saved);
    } else if (m?.type === 'preview') {
      $('preview').textContent = m.prompt;
    } else if (m?.type === 'error') {
      $('message').textContent = m.message; $('message').className = 'error';
    } else if (m?.type === 'notice') {
      $('message').textContent = m.message; $('message').className = 'muted';
    }
  });
  vscode.postMessage({ type: 'ready' });
}());
