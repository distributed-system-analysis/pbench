import pageRoutes from './router.config';

export default {
  define: {
    'process.env': process.env.NODE_ENV,
  },
  dynamicImport: undefined,
  base: '/dashboard',
  publicPath: process.env.NODE_ENV === 'development' ? '/' : '/dashboard/',
  ignoreMomentLocale: true,
  lessLoaderOptions: {
    javascriptEnabled: true,
  },
  routes: pageRoutes,
  plugins: [
    [
      'umi-plugin-react',
      {
        antd: true,
        dva: true,
      },
    ],
  ],
};
