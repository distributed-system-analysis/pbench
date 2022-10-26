import * as reactRedux from "react-redux";

import React from "react";
import ToastComponent from "./index";
import configureStore from "redux-mock-store";
import { render } from "@testing-library/react";

// test block
const mockStore = configureStore();
const initialState = {
  alerts: [
    {
      variant: "success",
      title: "Logged in successfully!",
      key: 112,
    },
    {
      variant: "success",
      title: "Saved!",
      key: 114,
    },
  ],
};
const store = mockStore(initialState);

describe("Test Toast Component", () => {
  beforeEach(() => {
    const mockDispatchFn = jest.fn();
    const useSelectorMock = jest.spyOn(reactRedux, "useSelector");
    const useDispatchMock = jest.spyOn(reactRedux, "useDispatch");

    useDispatchMock.mockReturnValue(mockDispatchFn);

    useSelectorMock.mockReturnValue(initialState.alerts);
  });
  // render the component on virtual dom
  it("Toast", () => {
    render(<ToastComponent store={store} />, {
      initialState,
    });

    expect(store.getActions()).toMatchSnapshot();
  });
});
