import * as reactRedux from "react-redux";

import { mockState, store } from "store/mockStore";

import React from "react";
import ToastComponent from "./index";
import { render } from "@testing-library/react";

describe("Test Toast Component", () => {
  beforeEach(() => {
    const mockDispatchFn = jest.fn();
    const useSelectorMock = jest.spyOn(reactRedux, "useSelector");
    const useDispatchMock = jest.spyOn(reactRedux, "useDispatch");

    useDispatchMock.mockReturnValueOnce(mockDispatchFn);

    useSelectorMock.mockReturnValueOnce(mockState.toastReducer);
  });
  // render the component on virtual dom
  it("Toast", () => {
    render(<ToastComponent store={store} />, {
      mockState,
    });

    expect(store.getActions()).toMatchSnapshot();
  });
});
