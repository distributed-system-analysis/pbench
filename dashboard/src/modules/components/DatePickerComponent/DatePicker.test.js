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
test("data is filtered based on date range selected from date picker", async () => {
  render(<AppWrapper />);
  await screen.findByText("dhcp1");
  const datePickerInput = screen.getAllByPlaceholderText(/yyyy-mm-dd/i);
  fireEvent.change(datePickerInput[0], { target: { value: "2022-02-16" } });
  fireEvent.change(datePickerInput[1], { target: { value: "2022-02-20" } });
  const updateBtn = screen.getByRole("button", { name: /update/i });
  fireEvent.click(updateBtn);
  const cells = screen.getAllByRole("cell");
  expect(cells).toHaveLength(12);
});
