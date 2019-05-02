import puppeteer from 'puppeteer';

let browser;
let page;

beforeAll(async () => {
  browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox'],
  });
  page = await browser.newPage();
  await page.goto('http://localhost:8000/dashboard/search', { waitUntil: 'networkidle2' });
});

afterAll(() => {
  browser.close();
});

describe('search page component', () => {
  test(
    'should load run mapping',
    async () => {
      await page.waitForResponse(response => response.status() === 200);
      await page.waitForSelector('.ant-table-tbody', { visible: true });
    },
    30000
  );

  test('should select search filter tag', async () => {
    await page.waitForSelector('.ant-tag', { visible: true });
    await page.click('.ant-tag');
  });

  test('should reset search filter tags', async () => {
    await page.waitForSelector('button[name="Reset"]', { visible: true });
    await page.click('button[name="Reset"]');
  });

  test('should input search query', async () => {
    await page.type('.ant-input', 'test', { delay: 50 });
  });

  test(
    'should execute search query',
    async () => {
      await page.waitForSelector('.ant-input-search-button', { visible: true });
      await page.click('.ant-input-search-button');
      await page.waitForResponse(response => response.status() === 200);
    },
    30000
  );

  test('should select month index', async () => {
    await page.waitForSelector('.ant-select-selection', { visible: true });
    await page.click('.ant-select-selection');
    await page.click('.ant-select-dropdown-menu-item');
    await page.click('.ant-select-dropdown-menu-item[aria-selected="false"]');
    await page.click('.ant-select-dropdown-menu-item[aria-selected="false"]');
  });

  test(
    'should update search results for selected month index',
    async done => {
      await page.waitForSelector('button[name="Apply"]', { visible: true });
      await page.click('button[name="Apply"]');
      await page.waitForResponse(response => response.status() === 200);
      await page.waitForSelector('.ant-table-tbody', { visible: true });
      done();
    },
    30000
  );
});
