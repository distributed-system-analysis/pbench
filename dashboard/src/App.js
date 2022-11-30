import "./App.css";
import "@patternfly/patternfly/patternfly.css";

import * as APP_ROUTES from "./utils/routeConstants";

import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
} from "react-router-dom";
import { COMING_SOON, NO_MATCH } from "assets/constants/navigationConstants";
import React, { useEffect } from "react";

import { AuthForm } from "modules/components/AuthComponent/common-components";
import AuthLayout from "modules/containers/AuthLayout";
import Cookies from "js-cookie";
import EmptyPage from "modules/components/EmptyPageComponent";
import LoginForm from "modules/components/AuthComponent/LoginForm";
import MainLayout from "modules/containers/MainLayout";
import OverviewComponent from "modules/components/OverviewComponent";
import ProfileComponent from "modules/components/ProfileComponent";
import SignupForm from "modules/components/AuthComponent/SignupForm";
import TableOfContent from "modules/components/TableOfContent";
import TableWithFavorite from "modules/components/TableComponent";
import { constructToast } from "actions/toastActions";
import favicon from "./assets/logo/favicon.ico";
import { fetchEndpoints } from "./actions/endpointAction";
import { getUserDetails } from "actions/authActions";
import { useDispatch } from "react-redux";

const ProtectedRoute = ({ redirectPath = APP_ROUTES.AUTH_LOGIN, children }) => {
  const loggedIn = Cookies.get("isLoggedIn");
  const dispatch = useDispatch();

  if (!loggedIn) {
    dispatch(constructToast("danger", "Please login to view the page"));
    return <Navigate to={redirectPath} replace />;
  }
  return children ? children : <Outlet />;
};

const HomeRoute = ({ redirectPath = APP_ROUTES.HOME }) => {
  return <Navigate to={redirectPath} replace />;
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
          <Route path="/" element={<HomeRoute />}></Route>
          <Route path={"/" + APP_ROUTES.HOME}>
            <Route element={<AuthLayout />}>
              <Route path={APP_ROUTES.AUTH_LOGIN} element={<LoginForm />} />
              <Route path={APP_ROUTES.AUTH} element={<AuthForm />} />
              <Route path={APP_ROUTES.AUTH_SIGNUP} element={<SignupForm />} />
            </Route>
            <Route element={<MainLayout />}>
              <Route index element={<TableWithFavorite />} />
              <Route element={<ProtectedRoute />}>
                <Route
                  path={APP_ROUTES.USER_PROFILE}
                  element={<ProfileComponent />}
                />
                <Route
                  path={APP_ROUTES.RESULTS}
                  element={<TableWithFavorite />}
                />
                <Route
                  path={APP_ROUTES.OVERVIEW}
                  element={<OverviewComponent />}
                />
                <Route
                  path={APP_ROUTES.TABLE_OF_CONTENT}
                  element={<TableOfContent />}
                />
                <Route
                  path={APP_ROUTES.ANALYSIS}
                  element={<EmptyPage text={COMING_SOON} />}
                />
              </Route>
            </Route>
            <Route
              path={APP_ROUTES.SEARCH}
              element={<EmptyPage text={COMING_SOON} />}
            />
            <Route
              path={APP_ROUTES.EXPLORE}
              element={<EmptyPage text={COMING_SOON} />}
            />
            <Route path="*" element={<EmptyPage text={NO_MATCH} />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </div>
  );
};

export default App;
