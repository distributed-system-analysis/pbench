import { Provider } from "react-redux";
import store from "store/store";
import App from "../../../App";
const { render, screen, fireEvent } = require("@testing-library/react");
const AppWrapper = () => {
  return (
    <Provider store={store}>
      <App />
    </Provider>
  );
};
test("Alert message is displayed on initial load", () => {
  render(<AppWrapper />);
  const alert = screen.getByText(/want to see your own data/i);
  expect(alert).toBeInTheDocument();
});

test("Alert message is closed on clicking close button", () => {
  render(<AppWrapper />);
  const alert = screen.getByText(/want to see your own data/i);
  const closeButton = screen.getByRole("button", {
    name: /close info alert/i,
  });
  fireEvent.click(closeButton);
  expect(alert).not.toBeVisible();
});
