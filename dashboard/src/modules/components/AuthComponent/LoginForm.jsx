import * as APP_ROUTES from "utils/routeConstants";

import {
  Alert,
  AlertGroup,
  Button,
  Card,
  CardBody,
  CardFooter,
  CardTitle,
  Checkbox,
  Form,
  FormGroup,
  TextInput,
} from "@patternfly/react-core";
import {
  Back,
  LoginHeader,
  NoLoginComponent,
  PasswordTextInput,
} from "./common-components";
import { EyeIcon, EyeSlashIcon } from "@patternfly/react-icons";
import React, { useCallback, useEffect, useState } from "react";
import { makeLoginRequest, setUserLoggedInState } from "actions/authActions";
import { useDispatch, useSelector } from "react-redux";

import { useOutletContext } from "react-router-dom";

const LoginForm = () => {
  const dispatch = useDispatch();
  const navigate = useOutletContext();
  const alerts = useSelector((state) => state.userAuth.alerts);
  const [details, setDetails] = useState({
    password: "",
    username: "",
  });
  const [btnDisabled, setBtnDisabled] = useState(true);
  const [showPassword, setShowPassword] = useState(false);

  const { endpoints } = useSelector((state) => state.apiEndpoint);
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
    dispatch(makeLoginRequest(details, navigate));
  };
  const checkOkButton = useCallback(() => {
    if (
      details.username?.length > 0 &&
      details.password?.length > 0 &&
      Object.keys(endpoints).length > 0
    ) {
      setBtnDisabled(false);
    } else {
      setBtnDisabled(true);
    }
  }, [details, endpoints]);

  const keepUser = useSelector((state) => state.userAuth.keepLoggedIn);
  const checkBoxChangeHander = (value) => {
    dispatch(setUserLoggedInState(value));
  };
  const onShowPassword = () => {
    setShowPassword(!showPassword);
  };
  useEffect(() => {
    checkOkButton();
  }, [checkOkButton, details]);

  const handleKeypress = (e) => {
    // it triggers by pressing the enter key
    if (e.charCode === 13) {
      sendLoginDetails();
    }
  };
  return (
    <Card>
      <CardTitle>
        <Back toPage={APP_ROUTES.AUTH} ctxtNav={navigate} />
        <LoginHeader title={"Login to your Pbench account"} />
        <AlertGroup isLiveRegion>
          {alerts.map(({ title, key }) => (
            <Alert variant="danger" title={title} key={key} />
          ))}
        </AlertGroup>
      </CardTitle>
      <CardBody>
        <Form>
          <FormGroup label="Username" isRequired fieldId="username">
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
            <div className="password-holder">
              <PasswordTextInput
                isRequired
                isShowPassword={showPassword}
                id="password"
                name="password"
                value={details.password}
                onChangeMethod={handlePasswordChange}
                onKeyPress={handleKeypress}
              />
              <Button
                variant="control"
                onClick={onShowPassword}
                icon={showPassword ? <EyeSlashIcon /> : <EyeIcon />}
              ></Button>
            </div>
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
            type="submit"
            onClick={sendLoginDetails}
            isDisabled={btnDisabled}
            {...primaryLoadingProps}
          >
            Login
          </Button>
        </div>
        <NoLoginComponent />
        <div className="orText text-center">-or-</div>
        <div className="text-center">
          <Button variant="link">Sign up</Button>
        </div>
      </CardFooter>
    </Card>
  );
};

export default LoginForm;
