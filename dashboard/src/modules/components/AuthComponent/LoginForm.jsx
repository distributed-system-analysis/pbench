import React, { useState, useCallback, useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";
import {
  Card,
  CardTitle,
  CardBody,
  CardFooter,
  Button,
  Form,
  FormGroup,
  TextInput,
  Checkbox,
  AlertGroup,
  Alert,
} from "@patternfly/react-core";
import {
  makeLoginRequest,
  setUserLoggedInState,
} from "../../../actions/authActions";
import { Back, LoginHeader, NoLoginComponent } from "./common-components";

const LoginForm = () => {
  const dispatch = useDispatch();
  const alerts = useSelector((state) => state.userAuth.alerts);
  const [details, setDetails] = useState({
    password: "",
    username: "",
  });
  const [btnDisabled, setBtnDisabled] = useState(true);
  const isLoading = useSelector((state) => state.loading.isLoading);
  const primaryLoadingProps = {};
  if (isLoading) {
    primaryLoadingProps.spinnerAriaValueText = "Loading";
    primaryLoadingProps.spinnerAriaLabelledBy = "primary-loading-button";
    primaryLoadingProps.isLoading = true;
  }
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
    dispatch(makeLoginRequest(details));
  };
  const checkOkButton = useCallback(() => {
    if (details.username?.length > 0 && details.password?.length > 0) {
      setBtnDisabled(false);
    } else {
      setBtnDisabled(true);
    }
  }, [details]);

  const keepUser = useSelector((state) => state.userAuth.keepLoggedIn);
  const checkBoxChangeHander = (value) => {
    dispatch(setUserLoggedInState(value));
  };
  useEffect(() => {
    checkOkButton();
  }, [checkOkButton, details]);

  return (
    <Card>
      <CardTitle>
        <Back toPage="/auth" />
        <LoginHeader title={"Login to your Pbench account"} />
        <AlertGroup isLiveRegion>
          {alerts.map(({ title, key }) => (
            <Alert variant="danger" title={title} key={key} />
          ))}
        </AlertGroup>
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
            isChecked={keepUser}
            onChange={checkBoxChangeHander}
            id="logged-in"
            name="logged-in"
          />
        </Form>
      </CardBody>
      <CardFooter>
        <div className="login-footer-btn-wrapper">
          <Button
            variant="primary"
            onClick={sendLoginDetails}
            isDisabled={btnDisabled}
            {...primaryLoadingProps}
          >
            Login
          </Button>
        </div>
        <NoLoginComponent />
      </CardFooter>
    </Card>
  );
};

export default LoginForm;
