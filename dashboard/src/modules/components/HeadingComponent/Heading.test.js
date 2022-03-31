import { Provider } from "react-redux";
import store from "store/store";
import App from "../../../App";
const { render, screen } = require("@testing-library/react");
const AppWrapper = () => {
  return (
    <Provider store={store}>
      <App />
    </Provider>
  );
};
test("Page heading is displayed on initial load", () => {
  render(<AppWrapper />);
  const heading = screen.getByRole("heading", { name: /controllers/i });
  expect(heading).toBeInTheDocument();
});
