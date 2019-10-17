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
    await page.waitForSelector('.ant-select:nth-child(1) > .ant-select-selection');
    const testMonth = await page.$eval(
      '.ant-select:nth-child(1) > .ant-select-selection > .ant-select-selection__rendered > ul > .ant-select-selection__choice',
      elem => elem.getAttribute('title')
    );
    expect(testMonth).toBe(mockIndices[0].index.split('.').pop());
  });

  test('should load mappings', async () => {
    await page.waitForSelector('.ant-select:nth-child(2) > .ant-select-selection');
    const testField = await page.$eval(
      '.ant-select:nth-child(2) > .ant-select-selection > .ant-select-selection__rendered > ul > .ant-select-selection__choice',
      elem => elem.getAttribute('title')
    );
    expect(testField).toBe('run.name');
  });

  test('should select month index', async () => {
    await page.waitForSelector('.ant-select:nth-child(1) > .ant-select-selection', {
      visible: true,
    });
    await page.click('.ant-select:nth-child(1) > .ant-select-selection');
    await page.click('.ant-select-dropdown-menu-item');
    await page.click('.ant-select-dropdown-menu-item[aria-selected="false"]');
  });

  test('should select field tag', async () => {
    await page.waitForSelector('.ant-select:nth-child(2) > .ant-select-selection', {
      visible: true,
    });
    await page.click('.ant-select:nth-child(2) > .ant-select-selection');
    await page.waitForSelector(
      '.ant-select-dropdown-menu > .ant-select-dropdown-menu-item-active',
      {
        visible: true,
      }
    );
    await page.click('.ant-select-dropdown-menu > .ant-select-dropdown-menu-item-active');
    await page.click(
      '.ant-select-dropdown-menu > .ant-select-dropdown-menu-item-active[aria-selected="false"]'
    );
  });

  test('should apply filter changes', async () => {
    await page.waitForSelector(
      '.ant-spin-container > .ant-form > .ant-row > div > .ant-btn-primary'
    );
    await page.click('.ant-spin-container > .ant-form > .ant-row > div > .ant-btn-primary');
  });

  test('should reset filter changes', async () => {
    await page.waitForSelector(
      '.ant-spin-container > .ant-form > .ant-row > div > .ant-btn-secondary'
    );
    await page.click('.ant-spin-container > .ant-form > .ant-row > div > .ant-btn-secondary');
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
