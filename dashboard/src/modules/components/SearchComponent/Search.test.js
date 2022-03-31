import { Provider } from "react-redux";
import store from "store/store";
import { MOCK_DATA } from "utils/mockData";
import App from "../../../App";
const { render, screen, fireEvent } = require("@testing-library/react");
const AppWrapper = () => {
  return (
    <Provider store={store}>
      <App />
    </Provider>
  );
};
jest.mock("utils/api", () => {
  return {
    get: () => ({
      data: MOCK_DATA,
    }),
  };
});
test("data is filtered based on value in search box", async () => {
  render(<AppWrapper />);
  await screen.findByText("dhcp1");
  const searchBox = screen.getByPlaceholderText(/search controllers/i);
  fireEvent.change(searchBox, { target: { value: "dhcp2" } });
  const searchBtn = screen.getByRole("button", {
    name: /searchButton/i,
  });
  fireEvent.click(searchBtn);
  const controllerTwo = screen.queryByText("dhcp2");
  const controllerThree = screen.queryByText("dhcp3");
  expect(controllerTwo).toBeInTheDocument();
  expect(controllerThree).not.toBeInTheDocument();
});
