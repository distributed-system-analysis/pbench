import * as ACTIONS from "../toastActions";

// import configureStore to create a mock store where we will dispatch our actions
import configureStore from "redux-mock-store";
// import thunk middle to make our action asynchronous
import thunk from "redux-thunk";

// initialise middlewares
const middlewares = [thunk];
// initialise MockStore which is only the configureStore method which take middlewares as its parameters
const mockStore = configureStore(middlewares);
const mockState = {
  alerts: [
    {
      variant: "success",
      title: "Logged in successfully!",
      message: 112,
      key: expect.anything(),
    },
    {
      variant: "success",
      title: "Saved!",
      message: 114,
      key: expect.anything(),
    },
  ],
};
const store = mockStore(mockState);
beforeAll(() => {
  // making getState as mock function and returning mock value
  store.getState = jest.fn().mockReturnValue(mockState);
});

afterAll(() => {
  jest.clearAllMocks();
  jest.resetAllMocks();
});

test("Show showFailureToast", () => {
  store.dispatch(ACTIONS.showFailureToast());

  expect(store.getActions()).toMatchSnapshot();
});

test("Show Toast", () => {
  store.dispatch(ACTIONS.showToast("success", "Logged in successfully!"));
  expect(store.getActions()).toMatchSnapshot();
});
