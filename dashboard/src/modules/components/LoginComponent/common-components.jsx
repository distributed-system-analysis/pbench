import React, { useState, useCallback,useEffect } from "react";
import "./index.less";
import {
  Card,
  CardTitle,
  CardBody,
  CardFooter,
  Button,
  Form,
  FormGroup,
  TextInput,
  Title,
  Flex,
  FlexItem,
  Checkbox
} from "@patternfly/react-core";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faAngleLeft } from "@fortawesome/free-solid-svg-icons";
import PBenchLogo from '../../../assets/logo/pbench_logo.svg';
import { useDispatch } from "react-redux";
import { makeLoginRequest } from "../../../actions/loginActions";

export const LoginForm = () => {
  const dispatch = useDispatch();
  
  const [details, setDetails] = useState({
    password: "",
    username: "",
  });
  const [btnDisabled, setBtnDisabled] = useState(true);
  const [isChecked, setIsChecked] = useState(false)
  const handleUsernameChange = (value) => {
    setDetails({
      ...details,
      username: value,
    });
  };
  const handlePasswordChange = (value) => {
    setDetails({
      ...details,
      password: value,
    });
  };
  const sendLoginDetails = () => {
    dispatch(makeLoginRequest(details))
  };
  const checkOkButton = useCallback(
    () => {
      if(details.username?.length > 0 && details.password?.length > 0) {
        setBtnDisabled(false)
      } else {
        setBtnDisabled(true)
      }
    },
    [details],
  );
  useEffect(() => {
    checkOkButton();
  },[checkOkButton, details])
  return (
    <Card>
      <CardTitle>
        {back}
        <LoginHeader title={"Login to your Pbench account"}/>
      </CardTitle>
      <CardBody>
        <Form>
          <FormGroup label="Email address" isRequired fieldId="username">
            <TextInput
              isRequired
              type="text"
              id="username"
              name="username"
              value={details.username}
              onChange={handleUsernameChange}
            />
          </FormGroup>
          <FormGroup label="Password" isRequired fieldId="password">
            <TextInput
              isRequired
              type="password"
              id="password"
              name="password"
              value={details.password}
              onChange={handlePasswordChange}
            />
          </FormGroup>
          <Checkbox
          label="Keep me logged in"
          isChecked={isChecked}
          onChange={(value) => setIsChecked(value)}
          id="logged-in"
          name="logged-in"
        />
        </Form>
      </CardBody>
      <CardFooter>
        <div className="login-footer-btn-wrapper">
          <Button variant="primary" onClick={sendLoginDetails} isDisabled={btnDisabled}>
            Login
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
};

export const LoginHeader = (props) => {
  return (
    <Title headingLevel="h3">{props.title}</Title>
  )
} 
export const back = (
  <Button
    id="backBtn"
    variant="link"
    icon={<FontAwesomeIcon icon={faAngleLeft} />}
    className={"back-button"}
    style={{ padding: "0 0 20px 5px" }}
  >
    Back
  </Button>
);

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
  const dispatch = useDispatch();

  return (
    <Card className="auth-card">
    <CardTitle><LoginHeader title="Login with..." /></CardTitle>
    <CardBody>
      <div className="button-wrapper">
        <Button variant="primary">Pbench Credentials</Button> 
      </div>
      <div className="account-wrapper">
        <div>
          <span>Need an account?</span>
          <Button variant="link">Sign up</Button>
        </div>
        <div><Button variant="link">Forgot your password</Button></div>
      </div>
    </CardBody>
    <CardFooter>
      <div className="log-in-alternate">Or log in with...</div>
      <div className="alternate-btn-wrapper">
        <Button variant="secondary">Red Hat SSO</Button>
        <Button variant="secondary">GitHub</Button>
        <Button variant="secondary">Gmail</Button>
      </div>
    </CardFooter>
  </Card>
  )
}