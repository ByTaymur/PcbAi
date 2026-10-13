// Side bar webview: text is rendered with textContent only; marker notes are data.
(function () {
  const vscode = acquireVsCodeApi();
  const $ = id => document.getElementById(id);
  const saved = vscode.getState() || {};
  $('request').value = saved.request || '';
  const chosen = () => [...document.querySelectorAll('#markers input:checked')].map(i => Number(i.value));
  const send = type => vscode.postMessage({ type, request: $('request').value, markers: chosen() });
  $('request').addEventListener('input', () => vscode.setState({ ...saved, request: $('request').value }));
  for (const button of document.querySelectorAll('[data-command]')) {
    button.addEventListener('click', () => vscode.postMessage({ type: 'command', command: button.dataset.command }));
  }
  $('pick').addEventListener('click', () => vscode.postMessage({ type: 'pick' }));
  $('reload').addEventListener('click', () => vscode.postMessage({ type: 'reload' }));
  $('open').addEventListener('click', () => send('open'));
  $('copy').addEventListener('click', () => send('copy'));
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
        const label = document.createElement('label'); label.className = 'marker' + (marker.open ? '' : ' closed');
        const box = document.createElement('input'); box.type = 'checkbox'; box.value = marker.n; box.checked = marker.open;
        const text = document.createElement('span'); text.textContent = marker.text + (marker.open ? '' : ' — ' + marker.status);
        label.append(box, text); list.append(label);
      }
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
