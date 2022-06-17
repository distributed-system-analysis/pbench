import { render, screen } from '@testing-library/react';
import App from './App';
import { Provider } from "react-redux";
import store from "store/store";
import React from 'react';

const AppWrapper = () => {
  return (
    <Provider store={store}>
      <App />
    </Provider>
  );
};

test('renders learn react link', () => {
  render(<AppWrapper />);
  const linkElement = screen.getByText('Explore');
  expect(linkElement).toBeInTheDocument();
});
