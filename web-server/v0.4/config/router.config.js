module.exports = [
  {
    path: '/',
    component: '../layouts/BasicLayout',
    routes: [
      {
        path: '/',
        name: 'dashboard',
        icon: 'dashboard',
        component: './Controllers',
      },
      {
        path: '/results',
        name: 'results',
        component: './Results',
      },
      {
        path: '/summary',
        name: 'summary',
        component: './Summary',
      },
      {
        path: '/comparison-select',
        name: 'comparison-select',
        component: './ComparisonSelect',
      },
      {
        path: '/comparison',
        name: 'comparison',
        component: './RunComparison',
      },
      {
        path: '/search',
        name: 'search',
        component: './Search',
      },
      {
        path: '/explore',
        name: 'explore',
        component: './Explore',
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
      {
        path: '/share/:id',
        name: 'share',
        component: './StaticLinkShare',
      },
    ],
  },
];
