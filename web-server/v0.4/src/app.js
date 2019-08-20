import { persistStore, persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

/*
 * redux persist configuration for saving state object to persisted storage.
 *
 * `dashboard` and `search` are blacklisted from the saved state as the namespaces
 * persist data that is constantly updated on the server side.
 */
const pathKey = window.location.pathname.split('/')[1];
const appPath = pathKey || 'dashboard';

const persistConfig = {
  timeout: 1000,
  key: appPath,
  storage,
  blacklist: ['dashboard', 'search', 'datastore'],
};

const persistEnhancer = () => createStore => (reducer, initialState, enhancer) => {
  const store = createStore(persistReducer(persistConfig, reducer), initialState, enhancer);
  const persist = persistStore(store, null);
  return {
    persist,
    ...store,
  };
};

// eslint-disable-next-line import/prefer-default-export
export const dva =
  process.env.APP_TYPE === 'build'
    ? {
        config: {
          extraEnhancers: [persistEnhancer()],
        },
      }
    : {
        config: {
          extraEnhancers: [persistEnhancer()],
        },
        plugins: [
          {
            // onAction: createLogger(),
          },
        ],
      };
