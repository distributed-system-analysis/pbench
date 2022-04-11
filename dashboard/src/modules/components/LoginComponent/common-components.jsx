import React, { useState, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
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
  Checkbox,
  HelperText,
  HelperTextItem,
} from "@patternfly/react-core";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faAngleLeft } from "@fortawesome/free-solid-svg-icons";
import { CheckIcon, CloseIcon, TimesIcon } from '@patternfly/react-icons';
import PBenchLogo from "../../../assets/logo/pbench_logo.svg";
import { useDispatch, useSelector } from "react-redux";
import { makeLoginRequest, 
  movePage, 
  setUserLoggedInState,
  registerUser } from "../../../actions/loginActions";
import { signupFormData, passwordConstraintsText } from "./signupFormData";
import { validateEmail, validatePassword } from "../../../utils/helper.js";

export const LoginForm = () => {
  const dispatch = useDispatch();

  const [details, setDetails] = useState({
    password: "",
    username: "",
  });
  const [btnDisabled, setBtnDisabled] = useState(true);
  const isLoading = useSelector(state => state.loading.isLoading);
  const primaryLoadingProps = {};
  if (isLoading) {
    primaryLoadingProps.spinnerAriaValueText = 'Loading';
    primaryLoadingProps.spinnerAriaLabelledBy = 'primary-loading-button';
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
  
  const keepUser = useSelector(state => state.userAuth.keepLoggedIn);
  const checkBoxChangeHander = (value) => {
    dispatch(setUserLoggedInState(value))
  }
  useEffect(() => {
    checkOkButton();
  }, [checkOkButton, details]);

  return (
    <Card>
      <CardTitle>
        <Back toPage="/auth" />
        <LoginHeader title={"Login to your Pbench account"} />
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
      </CardFooter>
    </Card>
  );
};

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
      </CardFooter>
    </Card>
  );
};

const PasswordConstraints = (props) => {
  const { checkConstraints } = props;
  const iconList = {
    'indeterminate': <TimesIcon style={{ color: '#D2D2D2' }} />,
    'success': <CheckIcon style={{ color: 'green' }} />,
    'error': <CloseIcon style={{ color: 'red' }} />
  }
  return (
    <>
      <h4>Passwords must contain at least:</h4>
      <div className="contraints-container">
        {passwordConstraintsText.map((constraint, index) => {
          let variant = checkConstraints[constraint.name]
          return (
            <HelperText key={index}>
              <HelperTextItem
                name={constraint.name}
                variant={checkConstraints[constraint.name]}
                icon={iconList[variant]}
              >
                {constraint.label}
              </HelperTextItem>
            </HelperText>
          );
        })}
      </div>
    </>
  );
};
export const SignupForm = () => {
  const [userDetails, setUserDetails] = useState({
    firstName: "",
    lastName: "",
    userName: "",
    email: "",
    password: "",
    passwordConfirm: "",
  });
  const [errors, setErrors] = useState({
    firstName: "",
    lastName: "",
    userName: "",
    email: "",
    passwordConstraints: "",
    passwordConfirm: "",
  });
  const [constraints, setConstraints] = useState({
    passwordLength: "indeterminate",
    passwordSpecialChars: "indeterminate",
    passwordContainsNumber: "indeterminate",
    passwordBlockLetter: "indeterminate",
  });

  const [btnDisabled, setBtnDisabled] = useState(true);
  const dispatch = useDispatch();

  const validateForm = useCallback(() => {
    if (
      userDetails.firstName?.trim() === "" ||
      userDetails.lastName?.trim() === "" ||
      userDetails.userName?.trim() === "" ||
      userDetails.email?.trim() === "" ||
      userDetails.password?.trim() === "" ||
      userDetails.passwordConfirm?.trim() === ""
    ) {
      return false;
    }
    // check if no errors.
    for (const dep of Object.entries(errors)) {
      if (dep[1].length > 0) {
        return false;
      }
    }
    // check if all constraints are met.
    for (const ct of Object.entries(constraints)) {
      if (ct[1] !== "success") {
        return false;
      }
    }
    // if we reach here, it means
    // we have covered all of the edge cases.
    return true;
  }, [constraints, errors, userDetails]);

  useEffect(() => {
    if (validateForm()) {
      setBtnDisabled(false);
    } else {
      setBtnDisabled(true);
    }
  }, [validateForm, userDetails]);

  const checkPasswordError = (password, cnfPassword) => {
    if (password !== cnfPassword) {
      setErrors({
        ...errors,
        passwordConfirm: "The above passwords do not match!",
      });
    } else {
      setErrors({ ...errors, passwordConfirm: "" });
    }
  };
  const changeHandler = (value, fieldName) => {
    setUserDetails({
      ...userDetails,
      [fieldName]: value,
    });
    if (fieldName === "email") {
      const isEmailValid = validateEmail(value);
      setErrors({
        ...errors,
        ...isEmailValid,
      });
    } else if (fieldName === "password") {
      const validPassword = validatePassword(value);
      setConstraints({
        ...constraints,
        ...validPassword,
      });
      // edge case where user deliberately
      // edits the password field, even when
      // confirm password is not empty.
      checkPasswordError(value, userDetails.confirmPassword);
    } else if (fieldName === "passwordConfirm") {
      checkPasswordError(userDetails.password, value);
    }
  };
  const sendForRegisteration = () => {
    let details = {
      email: userDetails.email,
      password: userDetails.password,
      first_name: userDetails.firstName,
      last_name: userDetails.lastName,
      username: userDetails.userName
    }
    dispatch(registerUser({...details}))
  }
  return (
    <Card className="signup-card">
      <CardTitle>
        <Back toPage="/auth" />
        <LoginHeader title="Create an account" />
      </CardTitle>
      <CardBody>
        <Form>
          {signupFormData.map((formItem, index) => {
            return (
              <FormGroup
                key={index}
                label={formItem.label}
                isRequired={formItem.isRequired}
                fieldId={formItem.id}
              >
                <TextInput
                  isRequired={formItem.isRequired}
                  type={formItem.type}
                  id={formItem.id}
                  aria-describedby="horizontal-form-name-helper"
                  name={formItem.name}
                  value={userDetails[formItem.name]}
                  onChange={(val) => changeHandler(val, formItem.name)}
                />
                <p className="error">{errors[formItem.name]}</p>
              </FormGroup>
            );
          })}
        </Form>
      </CardBody>
      <CardFooter>
        <PasswordConstraints checkConstraints={constraints} />
        <div className="button-wrapper">
          <Button variant="primary" isBlock isDisabled={btnDisabled}
          onClick={sendForRegisteration}>
            Create Account
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
};
