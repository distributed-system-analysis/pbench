import App from "./App";
import { Provider } from "react-redux";
import React from "react";
import { render } from "@testing-library/react";
import store from "store/store";

const AppWrapper = () => {
  return (
    <Provider store={store}>
      <App />
    </Provider>
  );
};

test("renders learn react link", () => {
  render(<AppWrapper />);
});
