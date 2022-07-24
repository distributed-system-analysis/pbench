import React, { useEffect } from "react";
import { useDispatch } from "react-redux";
import {
  BrowserRouter,
  Route,
  Routes,
  Navigate,
  Outlet,
} from "react-router-dom";
import favicon from "./assets/logo/favicon.ico";
import "./App.css";
import "@patternfly/patternfly/patternfly.css";
import * as APP_ROUTES from "./utils/routeConstants";
import MainLayout from "./modules/containers/MainLayout";
import AuthComponent from "./modules/components/AuthComponent";
import ProfileComponent from "modules/components/ProfileComponent";
import TableWithFavorite from "modules/components/TableComponent";
import { getUserDetails } from "actions/authActions";
import { constructToast } from "actions/toastActions";
import { fetchEndpoints } from "./actions/endpointAction";
import Cookies from "js-cookie";
import OverviewComponent from "modules/components/OverviewComponent";
import TableOfContent from "modules/components/TableOfContent";

const ProtectedRoute = ({ redirectPath = APP_ROUTES.AUTH_LOGIN, children }) => {
  const loggedIn = Cookies.get("isLoggedIn");
  const dispatch = useDispatch();

  if (!loggedIn) {
    dispatch(constructToast("danger", "Please login to view the page"));
    return <Navigate to={redirectPath} replace />;
  }
  return children ? children : <Outlet />;
};

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
            <Route element={<ProtectedRoute />}>
              <Route
                path={APP_ROUTES.USER_PROFILE}
                element={<ProfileComponent />}
              />
              <Route path="dashboard" element={<OverviewComponent />} />
            </Route>
          </Route>
          <Route path={APP_ROUTES.AUTH} element={<AuthComponent />} />
          <Route path={APP_ROUTES.AUTH_LOGIN} element={<AuthComponent />} />
          <Route path={APP_ROUTES.AUTH_SIGNUP} element={<AuthComponent />} />
          <Route path="/toc/*" element={<TableOfContent />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
};

export default App;
