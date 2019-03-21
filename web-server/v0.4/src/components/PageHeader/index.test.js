import { getBreadcrumb } from './index';
import { urlToList } from '../_utils/pathTools';

const routerData = {
  '/dashboard/results': {
    name: 'results',
  },
  '/search': {
    name: 'search',
  },
};

describe('test getBreadcrumb', () => {
  it('getBreadcrumb name for a simple url', () => {
    expect(getBreadcrumb(routerData, '/dashboard/results').name).toEqual('results');
  });

  it('getBreadcrumb for a single path', () => {
    const urlNameList = urlToList('/search').map(url => {
      return getBreadcrumb(routerData, url).name;
    });
    expect(urlNameList).toEqual(['search']);
  });
});
