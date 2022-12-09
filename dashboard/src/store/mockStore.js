// import configureStore to create a mock store where we will dispatch our actions
import configureStore from "redux-mock-store";
// import thunk middle to make our action asynchronous
import thunk from "redux-thunk";

// initialise middlewares
const middlewares = [thunk];

// initialise MockStore which is only the configureStore method which take middlewares as its parameters
const mockStore = configureStore(middlewares);

export const mockState = {
  toastReducer: {
    alerts: [
      {
        variant: "success",
        title: "Logged in successfully!",
        key: "test1",
        message: "",
      },
      {
        variant: "success",
        title: "Saved!",
        key: "test2",
        message: "",
      },
    ],
  },
};
export const store = mockStore(mockState);
