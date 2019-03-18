import { createStore } from 'redux';
import { persistStore, persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

const persistConfig = {
  timeout: 1000,
  key: 'root',
  storage,
};

const persistEnhancer = () => createStore => (reducer, initialState, enhancer) => {
  const store = createStore(persistReducer(persistConfig, reducer), initialState, enhancer);
  const persist = persistStore(store, null);
  return {
    persist,
    ...store,
  };
};
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
