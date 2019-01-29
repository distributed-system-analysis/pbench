import './polyfill';
import dva from 'dva';

/**
 * Use `history/createHashHistory` to support legacy web browsers.
 * Use `history/createBrowserHistory` for use in modern web browsers
 * that support the HTML5 History API.
 */
import createHistory from 'history/createBrowserHistory';
import createLoading from 'dva-loading';

import './index.less';
import 'ant-design-pro/dist/ant-design-pro.css';
// 1. Initialize
const app = dva({
  history: createHistory(),
});

// 2. Plugins
app.use(createLoading());

// 3. Register global model
app.model(require('./models/global').default);

// 4. Router
app.router(require('./router').default);

// 5. Start
app.start('#root');

export default app._store; // eslint-disable-line
