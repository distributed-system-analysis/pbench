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
      status:200
    }),
  };
});
test("data is filtered based on date range selected from date picker", async () => {
  render(<AppWrapper />);
  await screen.findByText("pbench_user_benchmark1");
  const datePickerInput = screen.getAllByPlaceholderText('YYYY-MM-DD');
  fireEvent.change(datePickerInput[0], { target: { value: "2022-02-16" } });
  fireEvent.change(datePickerInput[1], { target: { value: "2022-02-20" } });
  const updateBtn = screen.getByRole("button", { name: 'Update'});
  fireEvent.click(updateBtn);
  const datasetNameOne = screen.queryByText("pbench_user_benchmark1");
  const datasetNameTwo = screen.queryByText("pbench_user_benchmark2");
  const datasetNameThree = screen.queryByText("pbench_user_benchmark3");
  const datasetNameFour = screen.queryByText("pbench_user_benchmark4");
  const datasetNameFive = screen.queryByText("pbench_user_benchmark5");
  expect(datasetNameOne).toBeInTheDocument();
  expect(datasetNameTwo).toBeInTheDocument();
  expect(datasetNameThree).toBeInTheDocument();
  expect(datasetNameFour).not.toBeInTheDocument();
  expect(datasetNameFive).not.toBeInTheDocument();
});
