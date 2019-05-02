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

describe('results page component', () => {
  test(
    'should navigate to result',
    async done => {
      await page.waitForResponse(response => response.status() === 200);
      await page.waitForSelector('.ant-table-tbody', { visible: true });
      await page.waitForSelector('.ant-table-row[data-row-key]', { visible: true });
      await page.click('.ant-table-row[data-row-key]');
      done();
    },
    30000
  );

  test('should search for result name', async () => {
    await page.waitForSelector('.ant-table-row[data-row-key]', { visible: true });
    const result = await page.$eval('.ant-table-row', elem => elem.getAttribute('data-row-key'));
    await page.type('.ant-input', result, { delay: 50 });
    await page.click('.ant-input-search-button');
    await page.waitForSelector(`.ant-table-row[data-row-key="${result}"]`, { visible: true });
  });

  test('should reset search results', async () => {
    await page.click('.ant-input-suffix');
    await page.waitForSelector('.ant-table-row[data-row-key]', { visible: true });
  });

  test('should sort result column alphabetically', async () => {
    await page.$eval('.ant-table-column-title', elem => elem.click());
  });

  test('should sort start time column chronologically', async done => {
    await page.$$eval('.ant-table-column-title', elem => {
      if (elem.innerText === 'Start Time') {
        return elem.click();
      }
      return elem;
    });
    done();
  });
});
