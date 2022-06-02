import React, { useEffect } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import favicon from "./assets/logo/favicon.ico";
import "./App.css";
import * as APP_ROUTES from "./utils/routeConstants";
import AuthComponent from "./modules/components/AuthComponent";
import "@patternfly/patternfly/patternfly.css";
import MainLayout from "modules/containers/MainLayout";
import { useDispatch } from "react-redux";
import { fetchEndpoints } from "./actions/endpointAction";

const App = () => {
  const dispatch = useDispatch();

  useEffect(() => {
    const faviconLogo = document.getElementById("favicon");
    faviconLogo?.setAttribute("href", favicon);

    dispatch(fetchEndpoints);
  }, [dispatch]);

  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<MainLayout />} />
          <Route path={APP_ROUTES.AUTH} element={<AuthComponent />} />
          <Route path={APP_ROUTES.AUTH_LOGIN} element={<AuthComponent />} />
          <Route path={APP_ROUTES.AUTH_SIGNUP} element={<AuthComponent />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
};

export default App;
