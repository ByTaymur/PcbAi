// Actual Chromium + actual board_view bridge + real service/CLI, using only disposable demo copies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const Module = require('node:module');
const { spawn } = require('node:child_process');
const { chromium } = require('playwright');
const { evidencePath } = require('./evidence_output');

const extensionRoot = path.resolve(__dirname, '..');
const root = path.resolve(extensionRoot, '../..');
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function main() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'pcbai-viewer-'));
  const python = process.env.PCBAI_TEST_PYTHON || 'python';
  const backend = spawn(python, [path.join(root, 'scripts/viewer_test_service.py'), tmp], {
    cwd: root, shell: false, windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'], env: process.env });
  let stderr='';backend.stderr.on('data',b=>stderr+=b);
  const deadline=setTimeout(()=>backend.kill(),360000);
  let browser, server, info, view, subscriptions=[];
  try {
    for(let i=0;i<150 && !fs.existsSync(path.join(tmp,'backend.json'));i++) {
      if(backend.exitCode!==null)throw new Error(stderr);await sleep(100);
    }
    info=JSON.parse(fs.readFileSync(path.join(tmp,'backend.json')));
    async function request(name,args={},route='/call') {
      const result=await fetch(`http://127.0.0.1:${info.port}${route}`,{method:'POST',
        headers:{Authorization:'Bearer '+info.token,'Content-Type':'application/json'},
        body:JSON.stringify({name,arguments:args}),signal:AbortSignal.timeout(150000)});
      return result.json();
    }
    async function backgroundJob(tool,session,document) {
      const submitted=await request('start_job',{tool,session:session.id,document,revision:session.revision});
      assert.equal(submitted.ok,true,JSON.stringify(submitted));
      for(let i=0;i<1500;i++) {
        const response=await request('job_status',{job_id:submitted.job.job_id});
        if(['completed','failed'].includes(response.job.status)) {
          assert.equal(response.job.result.ok,true,JSON.stringify(response.job.result));return response.job.result;
        }
        await sleep(100);
      }
      throw new Error('Background job timeout');
    }
    const resources=new Map();let html='',receive,page,posted=[];
    server=http.createServer((req,res)=>{
      if(req.url==='/') {res.setHeader('Content-Type','text/html');res.end(html);return;}
      const file=resources.get(req.url);
      if(!file){res.writeHead(404);res.end();return;}
      const ext=path.extname(file);
      res.setHeader('Content-Type',{'.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml'}[ext] || 'text/plain');
      res.end(fs.readFileSync(file));
    });
    await new Promise(r=>server.listen(0,'127.0.0.1',r));
    const origin=`http://127.0.0.1:${server.address().port}`;
    const uri=p=>({fsPath:p,toString:()=>p});
    const makeUri = resource => {
      const file=resource.fsPath;
      // Module-relative imports need sibling URLs, not unrelated random asset IDs.
      let url;
      if(file.startsWith(path.join(extensionRoot,'media')+path.sep))url='/media/'+path.relative(path.join(extensionRoot,'media'),file).replaceAll('\\','/');
      else url='/views/'+path.relative(info.state,file).replaceAll('\\','/');
      resources.set(url,file);
      return {toString:()=>origin+url};
    };
    for(const name of ['viewer.css','viewer.js','vendor/three-bundle.js'])makeUri(uri(path.join(extensionRoot,'media',name)));
    const vscode={Uri:{file:uri},ViewColumn:{Beside:2},env:{clipboard:{writeText:async text=>{vscode.clipboard=text;}}},
      window:{createWebviewPanel:()=>{
        let dispose=()=>{};
        return {webview:{cspSource:origin,asWebviewUri:makeUri,
          onDidReceiveMessage:fn=>{receive=fn;return{dispose(){}};},
          postMessage:async message=>{posted.push(message);if(page)await page.evaluate(m=>window.dispatchEvent(new MessageEvent('message',{data:m})),message);return true;},
          set html(value){html=value;},get html(){return html;}},
          onDidDispose:fn=>{dispose=fn;},dispose:()=>dispose()};
      }}};
    const load=Module._load;
    Module._load=function(name,...args){return name==='vscode'?vscode:load.call(this,name,...args);};
    let openView;
    try {({openView}=require('../board_view'));} finally {Module._load=load;}
    browser=await chromium.launch({headless:true});
    const context=await browser.newContext({viewport:{width:1280,height:800}});
    const results=[];
    const errors=[];
    for(const session of info.sessions) {
      const document=session.project.replace(/\.kicad_pro$/,'.kicad_pcb');
      const demo=path.basename(session.root);
      page=await context.newPage();page.on('pageerror',e=>errors.push(String(e)));
      await page.exposeFunction('__send',m=>receive(m));
      await page.addInitScript(()=>{
        let state;
        window.acquireVsCodeApi=()=>({postMessage:m=>window.__send(m),getState:()=>state,setState:v=>{state=v;}});
      });
      view=openView({extensionPath:extensionRoot,subscriptions},{stateDir:info.state,session,document,
        call:request,backgroundJob,viewCall:(name,args)=>request(name,args,'/view/call')});
      await page.goto(origin);
      assert.equal((await view.whenReady).ready,true);
      await page.waitForFunction(()=>document.querySelector('#revision').textContent.includes('·'),null,{timeout:30000});
      const scene=await request('scene_pcb',{session:session.id,document,revision:session.revision});
      const footprints=scene.scene.items.filter(i=>i.type==='footprint');
      // Enable both copper layers so every footprint is selectable.
      for(const name of ['F.Cu','B.Cu'])await page.locator(`input[data-layer="${name}"]`).check();
      async function clickMm(p) {
        const render=(await request('render_pcb',{session:session.id,document,revision:(await request('pcbai_status')).sessions.find(s=>s.id===session.id).revision})).render;
        const m=render.mm_to_svg,position=await page.evaluate(({m,p})=>{
          const point=new DOMPoint(m[0]*p[0]+m[2]*p[1]+m[4],m[1]*p[0]+m[3]*p[1]+m[5]).matrixTransform(document.querySelector('#board').getScreenCTM());
          return{x:point.x,y:point.y};
        },{m,p});
        await page.mouse.click(position.x,position.y);
      }
      let clicked=0;
      for(const fp of footprints) {
        await clickMm(fp.at);
        const selected=await page.locator('#info').textContent();
        assert.ok(selected.includes(fp.reference+' ·'),`${demo} expected ${fp.reference}, got ${selected}`);clicked++;
      }
      const before=await page.locator('#board').getAttribute('viewBox');
      await page.locator('#board').hover();await page.mouse.wheel(0,-200);
      const after=await page.locator('#board').getAttribute('viewBox');assert.notEqual(before,after);
      // Left-drag pans without changing the selection; arrow keys pan too.
      const infoBefore=await page.locator('#info').textContent(),bb=await page.locator('#board').boundingBox();
      await page.mouse.move(bb.x+bb.width/2,bb.y+bb.height/2);await page.mouse.down();
      await page.mouse.move(bb.x+bb.width/2+120,bb.y+bb.height/2,{steps:6});await page.mouse.up();
      const dragged=(await page.locator('#board').getAttribute('viewBox')).split(/\s+/).map(Number);
      assert.ok(dragged[0]<Number(after.split(/\s+/)[0]),'drag did not pan');
      assert.equal(await page.locator('#info').textContent(),infoBefore,'drag changed the selection');
      await page.keyboard.press('ArrowRight');
      assert.ok(Number((await page.locator('#board').getAttribute('viewBox')).split(/\s+/)[0])>dragged[0],'arrow did not pan');
      await page.locator('#fit').click();
      await page.locator('#drc').click();
      await page.waitForFunction(()=>document.querySelector('#finding-list').textContent.includes('ev-'),null,{timeout:120000});
      const findings=posted.filter(m=>m.type==='drc').at(-1).findings;
      const positions=findings.flatMap(f=>(f.items || []).filter(i=>Number.isFinite(i.pos?.x) && Number.isFinite(i.pos?.y)).map(i=>[i.pos.x,i.pos.y]));
      assert.equal(await page.locator('#findings circle').count(),positions.length);
      const drawn=await page.locator('#findings circle').evaluateAll(nodes=>nodes.map(n=>[+n.getAttribute('cx'),+n.getAttribute('cy')]));
      const mapping=posted.filter(m=>m.type==='scene').at(-1).render.mm_to_svg;
      for(let i=0;i<positions.length;i++) {
        const [x,y]=positions[i];assert.ok(Math.hypot(drawn[i][0]-(mapping[0]*x+mapping[2]*y+mapping[4]),drawn[i][1]-(mapping[1]*x+mapping[3]*y+mapping[5]))<.0001);
      }
      // Real marker preview/apply persists without changing the board, with no HTML interpretation.
      const boardPath=path.join(session.root,document), original=fs.readFileSync(boardPath);
      await page.locator('#note').fill('İz 1 mm olsun <script>window.pwned=1</script>');
      await page.locator('[data-tool="point"]').click();await clickMm(footprints[0].at);
      try { await page.locator('#preview').waitFor({state:'visible'}); }
      catch(error) { console.error(demo,await page.locator('#error').textContent());throw error; }
      assert.equal(fs.existsSync(path.join(session.root,'pcbai/markers.json')),false);
      await page.locator('#apply').click();await page.locator('.marker[data-n="1"]').waitFor();
      assert.equal(await page.evaluate(()=>window.pwned),undefined);
      assert.deepEqual(fs.readFileSync(boardPath),original);
      const markers=await request('get_markers',{session:session.id});assert.equal(markers.markers[0].trusted,true);
      if(demo==='ecc83') {
        await page.locator('.marker[data-n="1"] button').filter({hasText:'Düzenle'}).click();
        await page.locator('#note').fill('Düzenlenmiş not');await page.locator('#edit-preview').click();
        await page.locator('#preview').waitFor({state:'visible'});await page.locator('#apply').click();
        await page.waitForFunction(()=>document.querySelector('.marker[data-n="1"] p').textContent==='Düzenlenmiş not');
        for(const kind of ['line','area','item']) {
          await page.locator('#note').fill(kind+' test');
          if(kind==='item') {await clickMm(footprints[0].at);await page.locator('#anchor').click();}
          else {
            await page.locator(`[data-tool="${kind}"]`).click();
            const b=scene.scene.bbox;
            await clickMm([b[0]+3,b[1]+3]);await clickMm([b[0]+7,b[1]+3]);
            if(kind==='area'){await clickMm([b[0]+7,b[1]+7]);await page.locator('#finish').click();}
          }
          await page.locator('#preview').waitFor({state:'visible'});await page.locator('#apply').click();
          const n={line:2,area:3,item:4}[kind];await page.locator(`.marker[data-n="${n}"]`).waitFor();
        }
        const saved=await request('get_markers',{session:session.id});assert.deepEqual(saved.markers.map(m=>m.kind),['point','line','area','item']);
        assert.equal(saved.markers[3].binding,'bound');
        await page.locator('.marker[data-n="2"] button').filter({hasText:'Sil'}).click();
        await page.locator('#preview').waitFor({state:'visible'});await page.locator('#apply').click();
        await page.locator('.marker[data-n="2"]').waitFor({state:'detached'});
      }
      await page.locator('.marker[data-n="1"] button').filter({hasText:'Ajana sor'}).click();
      await page.waitForFunction(()=>document.querySelector('#error').textContent.includes('panoya'));
      assert.ok(vscode.clipboard.includes('#1'));assert.ok(!html.includes(info.token));
      // Reopen the panel: state comes from the project, not browser memory.
      view.panel.dispose();await page.close();
      const readyAt=[];
      page=await context.newPage();await page.exposeFunction('__send',m=>{if(m?.type==='sceneReady')readyAt.push({at:Date.now(),revision:m.revision});return receive(m);});
      await page.addInitScript(()=>{window.acquireVsCodeApi=()=>({postMessage:m=>window.__send(m),getState:()=>null,setState:()=>{}});});
      view=openView({extensionPath:extensionRoot,subscriptions},{stateDir:info.state,session,document,
        call:request,backgroundJob,viewCall:(name,args)=>request(name,args,'/view/call')});
      await page.goto(origin);await page.locator('.marker[data-n="1"]').waitFor({timeout:30000});
      // G5: a saved change → bridge poll → render → every layer image decoded in the webview (sceneReady).
      const samples=[];
      for(let run=0;run<(demo==='ecc83'?10:1);run++) {
        const started=Date.now();fs.appendFileSync(boardPath,'\n');
        const changed=(await request('pcbai_status')).sessions.find(s=>s.id===session.id).revision;
        while(!readyAt.some(r=>r.revision===changed) && Date.now()-started<30000)await sleep(20);
        const ready=readyAt.find(r=>r.revision===changed);assert.ok(ready,'refresh did not complete');
        samples.push(ready.at-started);
      }
      await page.waitForFunction(()=>document.querySelector('#revision').textContent.includes('·'));
      const sorted=[...samples].sort((a,b)=>a-b);
      const refreshedMs=sorted[Math.floor((sorted.length-1)/2)];
      const refreshP95=sorted[Math.min(sorted.length-1,Math.round(.95*(sorted.length-1)))];
      await page.screenshot({path:evidencePath(root,'.pcbai-state/viewer-e2e/'+demo+'.png')});
      results.push({demo,footprints_clicked:clicked,drc_positions_checked:positions.length,marker_persisted:true,
        marker_edit_delete_all_kinds_checked:demo==='ecc83',source_bytes_unchanged_by_marker:true,refresh_ms:refreshedMs,refresh_p95_ms:refreshP95,refresh_samples_ms:samples});
      view.panel.dispose();await page.close();page=null;
    }
    assert.deepEqual(errors,[]);
    const report=evidencePath(root,(process.env.PCBAI_PUBLISH_EVIDENCE==='1'?'docs/spikes':'.pcbai-state')+'/G1-browser-result.json');
    fs.writeFileSync(report,JSON.stringify({browser:browser.version(),boards:results},null,2));
    console.log(JSON.stringify(results,null,2));
  } finally {
    if(view)view.panel.dispose();for(const s of subscriptions)s.dispose();
    if(browser)await browser.close();if(server)await new Promise(r=>server.close(r));
    if(info)await fetch(`http://127.0.0.1:${info.port}/shutdown`,{method:'POST',headers:{Authorization:'Bearer '+info.token},signal:AbortSignal.timeout(5000)}).catch(()=>{});
    if(backend.exitCode===null) {await Promise.race([new Promise(r=>backend.on('exit',r)),sleep(5000)]);if(backend.exitCode===null)backend.kill();}
    clearTimeout(deadline);
    assert.equal(path.dirname(path.resolve(tmp)),path.resolve(os.tmpdir()));fs.rmSync(tmp,{recursive:true,force:true});
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
