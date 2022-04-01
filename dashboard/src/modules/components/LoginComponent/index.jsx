import React, { useEffect } from "react";
import BackgroundCard from "../BackgroundComponent/index";
import { Grid, GridItem } from "@patternfly/react-core";
import { LoginForm, LoginRightComponent, AuthForm } from "./common-components";
import "./index.less";

const LoginComponent = () => {
  useEffect(() => {
    
  })
  
  return (
    <BackgroundCard>
      <div className="login-wrapper">
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
            <AuthForm />
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

export default LoginComponent;
