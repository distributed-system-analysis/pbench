import { urlToList } from '../_utils/pathTools';
import { getFlatMenuKeys, getMenuMatchKeys } from './SiderMenu';

const menu = [
  {
    path: '/dashboard',
    children: [
      {
        path: '/dashboard/results',
      },
      {
        path: '/dashboard/summary',
      },
      {
        path: '/dashboard/comparison-select',
      },
      {
        path: '/dashboard/comparison',
      },
    ],
  },
  {
    path: '/search',
  },
  {
    path: '/exception/404',
  },
  {
    path: '/exception/403',
  },
  {
    path: '/exception/500',
  },
];

const flatMenuKeys = getFlatMenuKeys(menu);

describe('test convert nested menu to flat menu', () => {
  it('simple menu', () => {
    expect(flatMenuKeys).toEqual([
      '/dashboard',
      '/dashboard/results',
      '/dashboard/summary',
      '/dashboard/comparison-select',
      '/dashboard/comparison',
      '/search',
      '/exception/404',
      '/exception/403',
      '/exception/500',
    ]);
  });
});

describe('test menu match', () => {
  it('simple path', () => {
    expect(getMenuMatchKeys(flatMenuKeys, urlToList('/dashboard'))).toEqual(['/dashboard']);
  });

  it('error path', () => {
    expect(getMenuMatchKeys(flatMenuKeys, urlToList('/dashboardresult'))).toEqual([]);
  });

  it('secondary path', () => {
    expect(getMenuMatchKeys(flatMenuKeys, urlToList('/dashboard/results'))).toEqual([
      '/dashboard',
      '/dashboard/results',
    ]);
  });
});
