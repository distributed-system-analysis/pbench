import "./index.less";

import * as APP_ROUTES from "utils/routeConstants";

import {
  Button,
  Card,
  CardFooter,
  CardTitle,
  Flex,
  FlexItem,
  Title,
} from "@patternfly/react-core";
import { useDispatch } from "react-redux";
import { useNavigate, useOutletContext } from "react-router-dom";
import { authCookies } from "actions/authActions";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import PBenchLogo from "assets/logo/pbench_logo.svg";
import React, { useEffect } from "react";
import { faAngleLeft } from "@fortawesome/free-solid-svg-icons";
import { movePage } from "actions/authActions";
import { useKeycloak } from '@react-keycloak/web';

export const LoginHeader = (props) => {
  return <Title headingLevel="h3">{props?.title}</Title>;
};
export const Back = (props) => {
  const dispatch = useDispatch();
  const navigatePage = (toPage) => {
    dispatch(movePage(toPage, props.ctxtNav));
  };
  return (
    <Button
      id="backBtn"
      variant="link"
      icon={<FontAwesomeIcon icon={faAngleLeft} />}
      className={"back-button"}
      onClick={() => navigatePage(props?.toPage)}
      style={{ padding: "0 0 20px 5px" }}
    >
      Back
    </Button>
  );
};

export const LoginRightComponent = () => {
  return (
    <>
      <div>
        <img src={PBenchLogo} alt="pbench_logo" className="logo" />
      </div>
      <div className="sideGridItem">
        <Title headingLevel="h4" size="xl">
          Pbench is a harness that allows data collection from a variety of
          tools while running a benchmark. Pbench has some built-in script that
          run some common benchmarks.
        </Title>
      </div>
      <div className="sideGridItem">
        <Flex>
          <FlexItem>
            <h4>Terms of Use</h4>
          </FlexItem>
          <FlexItem>
            <h4>Help</h4>
          </FlexItem>
          <FlexItem>
            <h4>Privacy Policy</h4>
          </FlexItem>
        </Flex>
      </div>
    </>
  );
};

export const AuthForm = () => {
  const navigate = useOutletContext();
  const { keycloak } = useKeycloak();

  const dispatch = useDispatch();
  const navigatePage = (toPage) => {
    dispatch(movePage(toPage, navigate));
  };
  useEffect(() => {
    dispatch(authCookies());
  }, );
  return (
    <Card className="auth-card">
      <CardTitle>
        <LoginHeader title="Login with..." />
      </CardTitle>
      <CardFooter>
        <div className="alternate-btn-wrapper">
          <Button
            variant="primary"
            onClick={() => keycloak.login({redirectUri: navigatePage(APP_ROUTES.OVERVIEW)})}
          >
            Pbench OpenId
          </Button>
        </div>
        <NoLoginComponent />
      </CardFooter>
    </Card>
  );
};

export const NoLoginComponent = () => {
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const navigatePage = (toPage) => {
    dispatch(movePage(toPage, navigate));
  };
  return (
    <div className="section">
      Want to continue without login? Click{" "}
      <Button
        variant="link"
        className="continueBtn"
        onClick={() => navigatePage("/")}
      >
        here
      </Button>
    </div>
  );
};
