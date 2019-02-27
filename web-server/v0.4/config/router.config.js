module.exports = [
  {
    path: '/',
    component: '../layouts/BasicLayout',
    routes: [
      {
        path: '/',
        name: 'dashboard',
        icon: 'dashboard',
        component: './Dashboard/Controllers',
      },
      {
        path: '/results',
        name: 'results',
        component: './Dashboard/Results',
      },
      {
        path: '/summary',
        name: 'summary',
        component: './Dashboard/Summary',
      },
      {
        path: '/comparison-select',
        name: 'comparison-select',
        component: './Dashboard/ComparisonSelect',
      },
      {
        path: '/comparison',
        name: 'comparison',
        component: './Dashboard/RunComparison',
      },
      {
        path: '/search',
        name: 'search',
        component: './Search/SearchList',
      },
      {
        path: '/exception/403',
        name: 'exception-403',
        component: './Exception/403',
      },
      {
        path: '/exception/404',
        name: 'exception-404',
        component: './Exception/404',
      },
      {
        path: '/exception/500',
        name: 'exception-500',
        component: './Exception/500',
      },
    ],
  },
];