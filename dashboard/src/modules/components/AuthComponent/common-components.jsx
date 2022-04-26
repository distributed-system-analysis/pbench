import React from "react";
import { useNavigate } from "react-router-dom";
import "./index.less";
import {
  Card,
  CardTitle,
  CardBody,
  CardFooter,
  Button,
  Title,
  Flex,
  FlexItem,
  HelperText,
  HelperTextItem,
} from "@patternfly/react-core";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faAngleLeft } from "@fortawesome/free-solid-svg-icons";
import { CheckIcon, CloseIcon, TimesIcon } from "@patternfly/react-icons";
import PBenchLogo from "assets/logo/pbench_logo.svg";
import { useDispatch, useSelector } from "react-redux";
import { movePage } from "actions/authActions";
import { passwordConstraintsText } from "./signupFormData";

export const LoginHeader = (props) => {
  return <Title headingLevel="h3">{props.title}</Title>;
};
export const Back = (props) => {
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const navigatePage = (toPage) => {
    dispatch(movePage(toPage, navigate));
  };
  return (
    <Button
      id="backBtn"
      variant="link"
      icon={<FontAwesomeIcon icon={faAngleLeft} />}
      className={"back-button"}
      onClick={() => navigatePage(props.toPage)}
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
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const navigatePage = (toPage) => {
    dispatch(movePage(toPage, navigate));
  };
  return (
    <Card className="auth-card">
      <CardTitle>
        <LoginHeader title="Login with..." />
      </CardTitle>
      <CardBody>
        <div className="button-wrapper">
          <Button variant="primary" onClick={() => navigatePage("/login")}>
            Pbench Credentials
          </Button>
        </div>
        <div className="account-wrapper">
          <div>
            <span>Need an account?</span>
            <Button variant="link" onClick={() => navigatePage("/signup")}>
              Sign up
            </Button>
          </div>
          <div>
            <Button variant="link">Forgot your password</Button>
          </div>
        </div>
      </CardBody>
      <CardFooter>
        <div className="log-in-alternate">Or log in with...</div>
        <div className="alternate-btn-wrapper">
          <Button variant="secondary">Red Hat SSO</Button>
          <Button variant="secondary">GitHub</Button>
          <Button variant="secondary">Gmail</Button>
        </div>
        <NoLoginComponent />
      </CardFooter>
    </Card>
  );
};

export const PasswordConstraints = (props) => {
  const { checkConstraints } = props;
  const iconList = {
    indeterminate: <TimesIcon style={{ color: "#D2D2D2" }} />,
    success: <CheckIcon style={{ color: "green" }} />,
    error: <CloseIcon style={{ color: "red" }} />,
  };
  const passwordLength = useSelector((state) => state.userAuth.passwordLength);
  return (
    <>
      <h4>Passwords must contain at least:</h4>
      <div className="contraints-container">
        {passwordConstraintsText.map((constraint, index) => {
          let variant = checkConstraints[constraint.name];
          return (
            <HelperText key={index}>
              <HelperTextItem
                name={constraint.name}
                variant={checkConstraints[constraint.name]}
                icon={iconList[variant]}
              >
                {
                  constraint.name === "passwordLength" &&
                  passwordLength
                }{" "}{constraint.label}
              </HelperTextItem>
            </HelperText>
          );
        })}
      </div>
    </>
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
      Want to continue without login? Click {" "}
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
 