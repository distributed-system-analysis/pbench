import puppeteer from 'puppeteer';
import { mockStore } from '../../mock/api';

let browser;
let page;

beforeAll(async () => {
  browser = await puppeteer.launch({
    headless: false,
    slowMo: 100,
    args: ['--no-sandbox'],
  });
  page = await browser.newPage();
  await page.goto('http://localhost:8000/dashboard/#/');
  await page.setRequestInterception(true);
  page.on('request', request => {
    if (request.method() === 'POST' && request.postData().includes('url')) {
      request.respond({
        status: 200,
        contentType: 'application/json',
        headers: { 'Access-Control-Allow-Origin': '*' },
        body: JSON.stringify(mockStore),
      });
    } else {
      request.continue();
    }
  });
});

afterAll(() => {
  browser.close();
});

describe('session flow', () => {
  test('should generate user session', async () => {
    await page.waitForSelector('.anticon-share-alt > svg');
    await page.click('.anticon-share-alt > svg');

    await page.waitForSelector('.ant-input');
    await page.type('.ant-input', 'controller page test', { delay: 50 });

    await page.waitForSelector(
      '.ant-modal-wrap > .ant-modal > .ant-modal-content > .ant-modal-footer > .ant-btn-primary'
    );
    await page.click(
      '.ant-modal-wrap > .ant-modal > .ant-modal-content > .ant-modal-footer > .ant-btn-primary'
    );
  });

  test('should copy session link', async () => {
    await page.waitForSelector('.ant-btn');
    await page.click('.ant-btn');
  });
});
