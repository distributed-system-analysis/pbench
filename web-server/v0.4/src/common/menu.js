import { isUrl } from '../utils/utils';

const menuData = [
  {
    name: 'Dashboard',
    icon: 'dashboard',
    path: '/',
  },
  {
    name: 'Search',
    icon: 'search',
    path: '/search',
  },
];

function formatter(data, parentPath = '/', parentAuthority) {
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
    if (item.children) {
      result.children = formatter(item.children, `${parentPath}${item.path}/`, item.authority);
    }
    return result;
  });
}

const getMenuData = () => formatter(menuData);
export default getMenuData;
