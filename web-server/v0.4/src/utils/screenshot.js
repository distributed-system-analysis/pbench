// node screenshot.js 'http://localhost:8000/dashboard/#/'
const puppeteer = require('puppeteer');

const url = process.argv[2];
if (!url) {
  throw new Error('URL please');
}
async function run() {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  await page.goto(url);
  await page.screenshot({ path: 'screenshot.png' });
  browser.close();
}
run();
