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
const store = mockStore(mockState);

describe("Toast Actions", () => {
  beforeEach(() => {
    // making getState as mock function and returning mock value
    store.getState = jest.fn().mockReturnValueOnce(mockState);
    store.clearActions();
  });

  afterEach(() => {
    jest.clearAllMocks();
    jest.resetAllMocks();
  });
  test("Show Failure Toast", () => {
    const expectedActions = [
      {
        type: "SHOW_TOAST",
        payload: [
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
          {
            key: expect.anything(),
            variant: "danger",
            message: "Please try again later",
            title: "Something went wrong",
          },
        ],
      },
    ];

    return store.dispatch(ACTIONS.showFailureToast()).then(() => {
      expect(store.getActions()).toEqual(expectedActions);
    });
  });

  test("Show Toast", () => {
    const expectedOutput = {
      key: expect.anything(),
      variant: "success",
      title: "Data updated!",
      message: "",
    };

    store.dispatch(ACTIONS.showToast("success", "Data updated!"));
    const bestMacth = (output) => {
      return output.find((item) => item.title === "Data updated!");
    };

    const givenPayload = store.getActions()[0].payload;
    const actions = bestMacth(givenPayload);
    expect(actions).toEqual(expectedOutput);
  });
  test("Show Session Expired", () => {
    const expectedOutput = {
      key: expect.anything(),
      variant: "danger",
      title: "Session Expired",
      message: "Please login to continue",
    };

    store.dispatch(ACTIONS.showSessionExpired());
    const bestMatch = (output) => {
      return output.find((item) => item.title === "Session Expired");
    };
    const givenPayload = store.getActions()[0].payload;
    const actions = bestMatch(givenPayload);
    expect(actions).toEqual(expectedOutput);
  });
  test("Hide toast", async () => {
    await store.dispatch(ACTIONS.hideToast("test2"));
    const expectedActions = [
      {
        type: "SHOW_TOAST",
        payload: [
          {
            variant: "success",
            title: "Logged in successfully!",
            key: "test1",
            message: "",
          },
        ],
      },
    ];
    expect(store.getActions()).toEqual(expectedActions);
  });
});
