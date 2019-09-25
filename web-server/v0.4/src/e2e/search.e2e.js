import puppeteer from 'puppeteer';
import { mockIndices, mockMappings, mockSearch } from '../../mock/api';

let browser;
let page;

beforeAll(async () => {
  browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox'],
  });
  page = await browser.newPage();
  await page.goto('http://localhost:8000/dashboard/#/search/');
  await page.setRequestInterception(true);
  page.on('request', request => {
    if (request.method() === 'POST' && request.postData().includes('query_string')) {
      request.respond({
        status: 200,
        contentType: 'application/json',
        headers: { 'Access-Control-Allow-Origin': '*' },
        body: JSON.stringify(mockSearch),
      });
    } else if (request.method() === 'GET' && request.url().includes('indices')) {
      request.respond({
        status: 200,
        contentType: 'application/json',
        headers: { 'Access-Control-Allow-Origin': '*' },
        body: JSON.stringify(mockIndices),
      });
    } else if (request.method() === 'GET' && request.url().includes('mappings')) {
      request.respond({
        status: 200,
        contentType: 'application/json',
        headers: { 'Access-Control-Allow-Origin': '*' },
        body: JSON.stringify(mockMappings),
      });
    } else {
      request.continue();
    }
  });
});

afterAll(() => {
  browser.close();
});

describe('search page component', () => {
  test('should load month indices', async () => {
    await page.waitForSelector(
      '.ant-form-item-control > .ant-form-item-children > .ant-select > .ant-select-selection > .ant-select-selection__rendered'
    );
    const testMonth = await page.$eval(
      '.ant-select-selection > .ant-select-selection__rendered > ul > li.ant-select-selection__choice',
      elem => elem.getAttribute('title')
    );
    expect(testMonth).toBe(mockIndices[0].index.split('.').pop());
  });

  test('should load mappings', async () => {
    await page.waitForSelector(
      'div.ant-col.ant-col-md-24.ant-col-lg-7 > div > div.ant-card-body > div:nth-child(2) > p:nth-child(2) > span:nth-child(1)'
    );
    const testField = await page.$eval(
      'div.ant-col.ant-col-md-24.ant-col-lg-7 > div > div.ant-card-body > div:nth-child(2) > p:nth-child(2) > span:nth-child(1)',
      elem => elem.innerHTML
    );
    expect(testField).toBe('config');
  });

  test('should select month index', async () => {
    await page.waitForSelector('.ant-select-selection', { visible: true });
    await page.click('.ant-select-selection');
    await page.click('.ant-select-dropdown-menu-item');
    await page.click('.ant-select-dropdown-menu-item[aria-selected="false"]');
  });

  test('should select field tag', async () => {
    await page.waitForSelector('.ant-tag', { visible: true });
    await page.click('.ant-tag');
  });

  test('should apply filter changes', async () => {
    await page.waitForSelector(
      '.ant-card-head > .ant-card-head-wrapper > .ant-card-extra > div > .ant-btn-primary'
    );
    await page.click(
      '.ant-card-head > .ant-card-head-wrapper > .ant-card-extra > div > .ant-btn-primary'
    );
  });

  test('should reset filter changes', async () => {
    await page.waitForSelector(
      '.ant-card-head > .ant-card-head-wrapper > .ant-card-extra > div > .ant-btn:nth-child(1)'
    );
    await page.click(
      '.ant-card-head > .ant-card-head-wrapper > .ant-card-extra > div > .ant-btn:nth-child(1)'
    );
  });

  test('should input search query', async () => {
    await page.type('.ant-input', 'test', { delay: 50 });
  });

  test('should execute search query', async () => {
    await page.waitForSelector('.ant-input-search-button', { visible: true });
    await page.click('.ant-input-search-button');
    const testResult = await page.$eval(
      '.ant-table-tbody > tr > td:nth-child(2)',
      elem => elem.innerHTML
    );
    expect(testResult).toBe('test_run');
  });
});
