import puppeteer from 'puppeteer';

let browser;
let page;

beforeAll(async () => {
  browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox'],
  });
  page = await browser.newPage();
  await page.goto('http://localhost:8000/', { waitUntil: 'networkidle2' });
});

afterAll(() => {
  browser.close();
});

describe('controller page component', () => {
  test(
    'shoud load controllers',
    async done => {
      await page.waitForResponse(response => response.status() === 200);
      await page.waitForSelector('.ant-table-tbody', { visible: true });
      done();
    },
    30000
  );

  test('should search for controller name', async () => {
    await page.waitForSelector('.ant-table-row[data-row-key]', { visible: true });
    const controller = await page.$eval('.ant-table-row', elem =>
      elem.getAttribute('data-row-key')
    );
    await page.type('.ant-input', controller, { delay: 50 });
    await page.click('.ant-input-search-button');
    await page.waitForSelector(`.ant-table-row[data-row-key="${controller}"]`, { visible: true });
  });

  test('should reset search results', async () => {
    await page.click('.ant-input-suffix');
    await page.waitForSelector('.ant-table-row[data-row-key]', { visible: true });
  });

  test('should sort controllers column alphabetically', async () => {
    await page.$eval('.ant-table-column-title', elem => elem.click());
  });

  test('should sort last modified column chronologically', async () => {
    await page.$$eval('.ant-table-column-title', elem => {
      if (elem.innerText === 'Last Modified') {
        return elem.click();
      }
      return elem;
    });
  });

  test('should sort results column numerically', async () => {
    await page.$$eval('.ant-table-column-title', elem => {
      if (elem.innerText === 'Results') {
        return elem.click();
      }
      return elem;
    });
  });

  test('should select month index', async () => {
    await page.click('.ant-select-selection');
    await page.click('.ant-select-dropdown-menu-item');
    await page.click('.ant-select-dropdown-menu-item[aria-selected="false"]');
  });

  test(
    'should update controllers for selected month index',
    async done => {
      await page.click('button[name="Update"]');
      await page.waitForResponse(response => response.status() === 200);
      await page.waitForSelector('.ant-table-tbody', { visible: true });
      done();
    },
    30000
  );
});
