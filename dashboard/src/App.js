import React, { useEffect } from "react";
import { useDispatch } from "react-redux";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import favicon from "./assets/logo/favicon.ico";
import "./App.css";
import "@patternfly/patternfly/patternfly.css";
import * as APP_ROUTES from "./utils/routeConstants";
import MainLayout from "./modules/containers/MainLayout";
import AuthComponent from "./modules/components/AuthComponent";
import ProfileComponent from "modules/components/ProfileComponent";
import TableWithFavorite from "modules/components/TableComponent";
import { getUserDetails } from "actions/authActions";
import { fetchEndpoints } from "./actions/endpointAction";

const App = () => {
  const dispatch = useDispatch();

  useEffect(() => {
    const faviconLogo = document.getElementById("favicon");
    faviconLogo?.setAttribute("href", favicon);

    dispatch(fetchEndpoints);
    dispatch(getUserDetails());
  }, [dispatch]);

  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<MainLayout />}>
            <Route index element={<TableWithFavorite />} />
            <Route path="user-profile" element={<ProfileComponent />} />
          </Route>
          <Route path={APP_ROUTES.AUTH} element={<AuthComponent />} />
          <Route path={APP_ROUTES.AUTH_LOGIN} element={<AuthComponent />} />
          <Route path={APP_ROUTES.AUTH_SIGNUP} element={<AuthComponent />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
};

export default App;
