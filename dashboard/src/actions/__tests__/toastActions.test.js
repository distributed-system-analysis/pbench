import * as ACTIONS from "../toastActions";

import { mockState, store } from "store/mockStore";

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
    const expectedOutput = {
      key: expect.anything(),
      variant: "danger",
      message: "Please try again later",
      title: "Something went wrong",
    };
    store.dispatch(ACTIONS.showFailureToast());
    const bestMatch = (output) =>
      output.find((item) => item.title.includes("Something went wrong"));

    const givenPayload = store.getActions()[0].payload;
    const actions = bestMatch(givenPayload);
    expect(actions).toEqual(expectedOutput);
  });

  test("Show Toast", () => {
    const expectedOutput = {
      key: expect.anything(),
      variant: "success",
      title: "Data updated!",
      message: "",
    };

    store.dispatch(ACTIONS.showToast("success", "Data updated!"));
    const bestMatch = (output) =>
      output.find((item) => item.title === "Data updated!");

    const givenPayload = store.getActions()[0].payload;
    const actions = bestMatch(givenPayload);
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
    const bestMatch = (output) =>
      output.find((item) => item.title === "Session Expired");

    const givenPayload = store.getActions()[0].payload;
    const actions = bestMatch(givenPayload);
    expect(actions).toEqual(expectedOutput);
  });
  test("Hide toast", () => {
    const keyToHide = "test2";
    const expected = [
      {
        variant: "success",
        title: "Saved!",
        key: "test2",
        message: "",
      },
    ];
    store.dispatch(ACTIONS.hideToast(keyToHide));
    const bestMatch = (output) =>
      output.filter((item) => item.filter !== keyToHide);

    const givenPayload = store.getActions()[0].payload;
    const actions = bestMatch(givenPayload);
    expect(actions).toEqual(expect.not.arrayContaining(expected));
  });
});
