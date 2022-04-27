import React from "react";
import BackgroundCard from "../BackgroundComponent/index";
import { Grid, GridItem } from "@patternfly/react-core";
import * as cx from "classnames";
import { LoginRightComponent, AuthForm } from "./common-components";
import SignupForm from "./SignupForm";
import LoginForm from "./LoginForm";
import { useLocation, Navigate } from "react-router-dom";
import * as AppRoutes from "utils/routeConstants";
import "./index.less";
import Cookies from "js-cookie";

const LoginSignup = () => {
  let { pathname } = useLocation();
  return pathname.includes(AppRoutes.AUTH_LOGIN) ? (
    <LoginForm />
  ) : (
    <SignupForm />
  );
};

const AuthComponent = () => {
  let { pathname } = useLocation();
  const loggedIn = Cookies.get("isLoggedIn");
  if (loggedIn) {
    return <Navigate to="/" />;
  }
  const wrapperName = pathname.includes(AppRoutes.AUTH_SIGNUP)
    ? "signup-wrapper"
    : "login-wrapper";

  return (
    <BackgroundCard>
      <div className={cx("main-container", wrapperName)}>
        <Grid gutter="md" className="login-page">
          <GridItem
            sm={8}
            md={4}
            lg={4}
            smOffset={1}
            mdOffset={1}
            lgOffset={1}
            className={"form"}
          >
            {pathname.includes(AppRoutes.AUTH) ? <AuthForm /> : <LoginSignup />}
          </GridItem>
          <GridItem
            sm={11}
            md={5}
            lg={5}
            smOffset={9}
            mdOffset={6}
            lgOffset={6}
            className={"sideGrid"}
          >
            <div className="login-right-component">
              <LoginRightComponent />
            </div>
          </GridItem>
        </Grid>
      </div>
    </BackgroundCard>
  );
};

export default AuthComponent;
