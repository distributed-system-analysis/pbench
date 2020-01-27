import { persistStore, persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

import { getAppPath } from './utils/utils';

/*
 * redux persist configuration for saving state object to persisted storage.
 *
 * `dashboard` and `search` are blacklisted from the saved state as the namespaces
 * persist data that is constantly updated on the server side.
 */

const persistConfig = {
  throttle: 1000,
  key: getAppPath(),
  storage,
  whitelist: ['global', 'user'],
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
export const dva = {
  config: {
    extraEnhancers: [persistEnhancer()],
  },
};
