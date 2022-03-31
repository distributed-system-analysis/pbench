import { Provider } from "react-redux";
import store from "store/store";
import { MOCK_DATA } from "utils/mockData";
import App from "../../../App";
const {
  render,
  screen,
  waitFor,
  fireEvent,
} = require("@testing-library/react");
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

test("data from API is displayed on initial load", async () => {
  render(<AppWrapper />);
  const benchmarkName = await screen.findByText("pbench_user_benchmark1");
  const cells = await screen.findAllByRole("cell");
  await waitFor(() => expect(benchmarkName).toBeInTheDocument());
  await waitFor(() => expect(cells).toHaveLength(20));
});

test("row is favorited after clicking on favorite icon", async () => {
  render(<AppWrapper />);
  await screen.findByText("dhcp1");
  const starBtn = screen.getAllByRole("button", {
    name: /not starred/i,
  });
  fireEvent.click(starBtn[0]);
  fireEvent.click(starBtn[1]);
  const favoriteBtn = screen.getByRole("button", {
    name: /see favorites button/i,
  });
  fireEvent.click(favoriteBtn);
  const favoriteCell = screen.getAllByRole("cell");
  expect(favoriteCell).toHaveLength(8);
});
