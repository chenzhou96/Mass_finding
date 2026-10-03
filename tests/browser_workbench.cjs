/* Real browser flow checks. PubChem-only fixtures are explicitly synthetic. */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {chromium} = require('playwright');
const base = process.env.WORKBENCH_URL || 'http://127.0.0.1:8866';
const output = process.env.WORKBENCH_EVIDENCE || path.resolve('test-results');
const results=[];
const captureErrors=[];
async function test(name,fn){await fn();results.push({name,status:'passed'});console.log('PASS '+name);}
async function text(page,id){return page.locator('#'+id).textContent();}

(async()=>{
 await fs.mkdir(output,{recursive:true});
 const browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||'chrome',headless:true,chromiumSandbox:true});
 try {
  const context=await browser.newContext({viewport:{width:1366,height:768},acceptDownloads:true});
  const page=await context.newPage();page.on('pageerror',error=>captureErrors.push(error.message));
  await page.goto(base);await page.locator('#element-H').waitFor();
  await test('1366×768 real Chrome: ethanol truth and normal workflow visible',async()=>{
   await page.locator('#analyze').click();await page.waitForFunction(()=>document.getElementById('resultCount').textContent==='1');
   assert.match(await page.locator('#rows').innerText(),/C2H6O/);assert.match(await page.locator('#rows').innerText(),/47\.049141280/);
   const dbe=await page.locator('#dbe').boundingBox(),footer=await page.locator('.form-footer').boundingBox();assert(dbe.y<footer.y);assert(footer.y+footer.height<=768);
   await page.locator('#rows tr').click();await page.screenshot({path:path.join(output,'workbench-1366x768.png'),fullPage:true});
  });
  let saved;
  await test('JSON download retains original precision and full input provenance',async()=>{
   const downloadPromise=page.waitForEvent('download');await page.locator('#jsonExport').click();const download=await downloadPromise;
   saved=JSON.parse(await fs.readFile(await download.path(),'utf8'));
   assert.equal(saved.results[0].calculated_properties.molecular_weight,46.04186481295);assert.equal(saved.input_params.m2z,47.049141279571);assert.equal(saved.metadata.engine_version,'2.0.0');
  });
  await test('CSV download retains unrounded masses',async()=>{
   const promise=page.waitForEvent('download');await page.locator('#csvExport').click();const d=await promise;const raw=await fs.readFile(await d.path(),'utf8');assert(raw.includes('46.04186481295'));assert(raw.includes('47.049141279571'));assert(raw.includes('input_params'));
  });
  await test('1366×768 current candidates become stale immediately on edits',async()=>{
   await page.locator('#mz').fill('48');assert.equal(await page.locator('#jsonExport').isDisabled(),true);assert.equal(await page.locator('#addSearch').isDisabled(),true);assert.match(await text(page,'resultState'),/陈旧/);
  });
  await test('Malformed import preserves current inputs and prior result',async()=>{
   await page.locator('#importFile').setInputFiles({name:'synthetic-invalid.json',mimeType:'application/json',buffer:Buffer.from('{"results":[{}]}')});
   await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('无法打开'));assert.equal(await page.locator('#mz').inputValue(),'48');assert.equal(await text(page,'resultCount'),'1');
  });
  await test('Valid JSON import restores parameters without recalculation',async()=>{
   await page.locator('#importFile').setInputFiles({name:'synthetic-ethanol.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(saved))});
   await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('文件与输入已恢复'));assert.equal(await page.locator('#mz').inputValue(),'47.049141279571');assert.equal(await page.locator('#element-H').inputValue(),'12');assert.equal(await page.locator('#jsonExport').isEnabled(),true);
  });
  await test('Explicit H=0 excludes hydrogen rather than restoring unlimited H',async()=>{
   await page.locator('#element-H').fill('0');await page.locator('#analyze').click();await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('无候选'));assert.equal(await text(page,'resultCount'),'0');
  });
  await test('Unsupported multicharge adduct errors recover buttons',async()=>{
   await page.locator('#element-H').fill('12');await page.locator('#charge').fill('2');await page.locator('#adducts input[value="Na+"]').check();await page.locator('#analyze').click();await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('多电荷'));assert(await page.locator('#analyze').isEnabled());
  });
  await test('Double clicks issue one job; edited inputs never receive old response',async()=>{
   await page.locator('#example').click();let requests=0;
   await page.route('**/api/analyze',async route=>{requests++;await new Promise(r=>setTimeout(r,350));await route.continue();});
   await page.locator('#analyze').dblclick();await page.locator('#mz').fill('49');
   await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('未回填'));assert.equal(requests,1);assert.equal(await page.locator('#mz').inputValue(),'49');await page.unroute('**/api/analyze');
  });
  await test('Cancellation state never displays a finished result',async()=>{
   await page.locator('#example').click();let cancelled=false;
   await page.route('**/api/analyze',r=>r.fulfill({status:202,contentType:'application/json',body:'{"id":"synthetic-cancel"}'}));
   await page.route('**/api/jobs/synthetic-cancel',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({status:cancelled?'cancelled':'running'})}));
   await page.route('**/api/cancel/synthetic-cancel',r=>{cancelled=true;return r.fulfill({contentType:'application/json',body:'{}'});});
   await page.locator('#analyze').click();await page.locator('#cancel').click();await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('分析已取消'));assert(await page.locator('#analyze').isEnabled());
   await page.unroute('**/api/analyze');await page.unroute('**/api/jobs/synthetic-cancel');await page.unroute('**/api/cancel/synthetic-cancel');
  });
  await test('Cancel intent suppresses success that completed before first poll',async()=>{
   await page.locator('#example').click();
   await page.route('**/api/analyze',r=>r.fulfill({status:202,contentType:'application/json',body:'{"id":"synthetic-completed"}'}));
   await page.route('**/api/jobs/synthetic-completed',async r=>{await new Promise(resolve=>setTimeout(resolve,300));await r.fulfill({contentType:'application/json',body:JSON.stringify({status:'success',result:saved})});});
   await page.route('**/api/cancel/synthetic-completed',r=>r.fulfill({contentType:'application/json',body:'{}'}));
   await page.locator('#analyze').click();await page.locator('#cancel').click();await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('分析已取消'));assert.equal(await text(page,'resultCount'),'0');
   await page.unroute('**/api/analyze');await page.unroute('**/api/jobs/synthetic-completed');await page.unroute('**/api/cancel/synthetic-completed');
  });
  await test('V2 JSON with omitted H restores H=0 consistently with the shared engine',async()=>{
   const fixture=JSON.parse(JSON.stringify(saved));delete fixture.input_params.elements.H;fixture.results=[];
   await page.locator('#importFile').setInputFiles({name:'synthetic-v2-no-H.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(fixture))});
   await page.waitForFunction(()=>document.getElementById('element-H').value==='0');assert.equal(await page.locator('#element-H').inputValue(),'0');
  });
  await test('Legacy JSON restores implicit H with a clear historical result label',async()=>{
   const fixture=JSON.parse(JSON.stringify(saved));delete fixture.input_params.elements.H;delete fixture.metadata.engine_version;
   await page.locator('#importFile').setInputFiles({name:'synthetic-legacy-no-H.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(fixture))});
   await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('历史文件'));assert.equal(await page.locator('#element-H').inputValue(),'-1');assert.match(await text(page,'resultState'),/历史/);
   await page.locator('#example').click();
  });
  await test('1440×900 real Chrome: dense candidates, pagination, filter and pixel capture',async()=>{
   await page.setViewportSize({width:1440,height:900});await page.locator('#mz').fill('181.07066456');await page.locator('#pct').fill('0.1');
   for(const [e,n]of Object.entries({C:15,H:30,N:5,O:10}))await page.locator('#element-'+e).fill(String(n));
   await page.locator('#analyze').click();await page.waitForFunction(()=>Number(document.getElementById('resultCount').textContent)>25);
   await page.locator('#rows tr').first().click();await page.screenshot({path:path.join(output,'workbench-1440x900.png'),fullPage:true});
   assert(await page.locator('#next').isEnabled());await page.locator('#next').click();assert.match(await text(page,'pageLabel'),/^2/);await page.locator('#formulaFilter').fill('no such formula');assert.equal(await page.locator('#rows tr').count(),0);await page.locator('#formulaFilter').fill('');
  });
  await test('Small 820×620 window retains actions and local scrolling',async()=>{
   await page.setViewportSize({width:820,height:620});await page.locator('#settingsOpen').click();await page.locator('#precision').selectOption('6');await page.locator('#settingsClose').click();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert(await page.locator('#analyze').isVisible());assert(await page.locator('#next').isVisible());await page.screenshot({path:path.join(output,'workbench-820x620.png'),fullPage:true});
  });
  await test('Narrow 640×720 window keeps controls accessible with document scrolling',async()=>{
   await page.setViewportSize({width:640,height:720});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.locator('#jsonExport').scrollIntoViewIfNeeded();assert(await page.locator('#jsonExport').isVisible());await page.locator('#advancedElements summary').click();await page.locator('#element-Se').scrollIntoViewIfNeeded();assert(await page.locator('#element-Se').isVisible());await page.locator('#advancedElements summary').click();
  });
  await test('PubChem synthetic partial record renders missing fields and nonprobability label',async()=>{
   await page.setViewportSize({width:1366,height:768});await page.locator('#example').click();await page.locator('#analyze').click();await page.waitForFunction(()=>document.getElementById('resultCount').textContent==='1');await page.locator('#rows tr').click();await page.locator('#addSearch').click();
   const result={success:{C2H6O:{metadata:{status:'partial'},results:[{cid:702,title:'Synthetic ethanol record',molecular_weight:'46.07',monoisotopic_mass:46.04186481295,final_score:65,synonyms_complete:false,synonyms:[]}]}},partial:{C2H6O:{message:'synthetic synonym batch failure'}}};
   await page.route('**/api/search',r=>r.fulfill({status:202,contentType:'application/json',body:'{"id":"synthetic-partial"}'}));
   await page.route('**/api/jobs/synthetic-partial',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({status:'success',result})}));
   await page.locator('#queue button').filter({hasText:'查询 / 重试'}).first().click();await page.waitForFunction(()=>document.getElementById('searchStatus').textContent.includes('部分结果'));
   assert.match(await text(page,'compoundDetail'),/缺失/);assert.match(await text(page,'compoundDetail'),/≠ 鉴定概率/);await page.screenshot({path:path.join(output,'pubchem-synthetic-partial-1366x768.png'),fullPage:true});
   await page.unroute('**/api/search');await page.unroute('**/api/jobs/synthetic-partial');
  });
  await test('PubChem synthetic failure remains retryable',async()=>{
   await page.route('**/api/search',r=>r.fulfill({status:202,contentType:'application/json',body:'{"id":"synthetic-error"}'}));await page.route('**/api/jobs/synthetic-error',r=>r.fulfill({contentType:'application/json',body:'{"status":"error","error":"synthetic timeout"}'}));
   await page.locator('#queue button').filter({hasText:'查询 / 重试'}).first().click();await page.waitForFunction(()=>document.getElementById('queue').textContent.includes('保留待重试'));assert(await page.locator('#queue button').filter({hasText:'查询 / 重试'}).isEnabled());
   await page.unroute('**/api/search');await page.unroute('**/api/jobs/synthetic-error');
  });
  await test('Parameter draft restoration does not restore results',async()=>{
   await page.locator('.nav[data-view="analysis"]').click();await page.locator('#mz').fill('55');await page.reload();await page.locator('#element-H').waitFor();assert.equal(await page.locator('#mz').inputValue(),'55');assert.equal(await text(page,'resultCount'),'0');
  });
  await test('No browser JavaScript runtime errors',async()=>assert.deepEqual(captureErrors,[]));
  await fs.writeFile(path.join(output,'browser-results.json'),JSON.stringify({browser:await browser.version(),sandbox:true,real_browser:true,viewport_pixels_review_required:true,synthetic_pubchem:true,passed:results.length,results},null,2));
  console.log(`Browser workflows: ${results.length}/${results.length} passed`);
 } finally {await browser.close();}
})().catch(async error=>{console.error(error);await fs.mkdir(output,{recursive:true});await fs.writeFile(path.join(output,'browser-failure.json'),JSON.stringify({results,error:String(error)},null,2));process.exitCode=1;});
