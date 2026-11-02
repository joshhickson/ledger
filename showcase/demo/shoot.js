// Takes the showcase screenshots. Run from the repository root after render.py:  node showcase/demo/shoot.js
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const D = __dirname;
const OUT = path.join(D, 'screenshots');
(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const b = await chromium.launch();
  const shot = async (file, png, width, height) => {
    const pg = await b.newPage({ viewport: { width, height }, deviceScaleFactor: 2 });
    await pg.goto('file://' + file);
    await pg.screenshot({ path: path.join(OUT, png), fullPage: true });
    await pg.close();
  };
  for (const f of fs.readdirSync(path.join(D, 'pages')).sort()) {
    await shot(path.join(D, 'pages', f), f.replace('.html', '.png'), 1000, 400);
  }
  await shot(path.join(D, 'raw', 'ledger.html'), '6-ledger-page.png', 1200, 900);
  await shot(path.join(D, 'raw', 'ledger.html'), '6b-ledger-page-phone.png', 390, 844);
  await b.close();
  console.log(fs.readdirSync(OUT).sort().join('\n'));
})();
