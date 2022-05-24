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
      status: 200,
    }),
  };
});
test("Page heading is displayed on initial load", async () => {
  render(<AppWrapper />);
  await screen.findByText("pbench_user_benchmark1");
  const heading = screen.getByRole("heading", { name: 'Results' });
  expect(heading).toBeInTheDocument();
});
test("data from API is displayed on initial load", async () => {
  render(<AppWrapper />);
  await screen.findByText("pbench_user_benchmark1");
  const datasetNameOne = screen.queryByText("pbench_user_benchmark1");
  const datasetNameTwo = screen.queryByText("pbench_user_benchmark2");
  const datasetNameThree = screen.queryByText("pbench_user_benchmark3");
  const datasetNameFour = screen.queryByText("pbench_user_benchmark4");
  const datasetNameFive = screen.queryByText("pbench_user_benchmark5");
  expect(datasetNameOne).toBeInTheDocument();
  expect(datasetNameTwo).toBeInTheDocument();
  expect(datasetNameThree).toBeInTheDocument();
  expect(datasetNameFour).toBeInTheDocument();
  expect(datasetNameFive).toBeInTheDocument();
});

test("row is favorited after clicking on favorite icon", async () => {
  render(<AppWrapper />);
  await screen.findByText("pbench_user_benchmark1");
  const starBtn = screen.getAllByRole("button", {
    name: 'Not starred',
  });
  fireEvent.click(starBtn[0]);
  fireEvent.click(starBtn[1]);
  const favoriteBtn = screen.getByRole("button", {
    name: 'see favorites button',
  });
  fireEvent.click(favoriteBtn);
  const datasetNameOne = screen.queryByText("pbench_user_benchmark1");
  const datasetNameTwo = screen.queryByText("pbench_user_benchmark2");
  const datasetNameThree = screen.queryByText("pbench_user_benchmark3");
  const datasetNameFour = screen.queryByText("pbench_user_benchmark4");
  const datasetNameFive = screen.queryByText("pbench_user_benchmark5");
  expect(datasetNameOne).toBeInTheDocument();
  expect(datasetNameTwo).toBeInTheDocument();
  expect(datasetNameThree).not.toBeInTheDocument();
  expect(datasetNameFour).not.toBeInTheDocument();
  expect(datasetNameFive).not.toBeInTheDocument();
});
test("data is filtered based on value in search box", async () => {
  render(<AppWrapper />);
  await screen.findByText("pbench_user_benchmark1");
  const searchBox = screen.getByPlaceholderText('Search Dataset');
  fireEvent.change(searchBox, { target: { value: "pbench_user_benchmark2" } });
  const searchBtn = screen.getByRole("button", {
    name: 'searchButton',
  });
  fireEvent.click(searchBtn);
  const datasetNameTwo = screen.queryByText("pbench_user_benchmark2");
  const datasetNameThree = screen.queryByText("pbench_user_benchmark3");
  expect(datasetNameTwo).toBeInTheDocument();
  expect(datasetNameThree).not.toBeInTheDocument();
});
