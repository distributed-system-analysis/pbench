import { isUrl } from '../utils/utils';

const menuData = [
  {
    name: 'Dashboard',
    icon: 'dashboard',
    path: '/',
    routes: [
      {
        name: 'Results',
        path: '/results',
        routes: [
          {
            name: 'Summary',
            path: '/summary',
          },
          {
            name: 'Comparison Select',
            path: '/comparison-select',
            routes: [
              {
                name: 'Comparison',
                path: '/comparison',
              },
            ],
          },
        ],
      },
    ],
  },
  {
    name: 'Search',
    icon: 'search',
    path: '/search',
  },
  {
    name: 'Explore',
    icon: 'global',
    path: '/explore',
  },
];

function formatter(data, parentPath = '', parentAuthority) {
  return data.map(item => {
    let { path } = item;
    if (!isUrl(path)) {
      path = parentPath + item.path;
    }
    const result = {
      ...item,
      path,
      authority: item.authority || parentAuthority,
    };
    if (item.routes) {
      result.routes = formatter(item.routes, `${parentPath}${item.path}`, item.authority);
    }
    return result;
  });
}

const getMenuData = () => formatter(menuData);
export default getMenuData;
