import {
  Alert,
  AlertGroup,
  Button,
  Card,
  CardBody,
  CardFooter,
  CardTitle,
  Form,
  FormGroup,
  TextInput,
} from "@patternfly/react-core";
import {
  Back,
  LoginHeader,
  NoLoginComponent,
  PasswordConstraints,
  PasswordTextInput,
} from "./common-components";
import { EyeIcon, EyeSlashIcon } from "@patternfly/react-icons";
import React, { useCallback, useEffect, useState } from "react";
import { registerUser, toggleSignupBtn } from "actions/authActions";
import { useDispatch, useSelector } from "react-redux";
import { validateEmail, validatePassword } from "utils/helper.js";

import { signupFormData } from "./signupFormData";
import { useNavigate } from "react-router-dom";

const SignupForm = () => {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { endpoints } = useSelector((state) => state.apiEndpoint);
  const { alerts, isSignupBtnDisabled, passwordLength } = useSelector(
    (state) => state.userAuth
  );
  const [showPassword, setShowPassword] = useState(false);
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

  const onShowPassword = () => {
    setShowPassword(!showPassword);
  };

  useEffect(() => {
    if (validateForm() && Object.keys(endpoints).length > 0) {
      dispatch(toggleSignupBtn(false));
    } else {
      dispatch(toggleSignupBtn(true));
    }
  }, [validateForm, userDetails, dispatch, endpoints]);

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
      const validPassword = validatePassword(value, passwordLength);
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
  const sendForRegistration = () => {
    const details = {
      email: userDetails.email,
      password: userDetails.password,
      first_name: userDetails.firstName,
      last_name: userDetails.lastName,
      username: userDetails.userName,
    };
    dispatch(registerUser({ ...details }, navigate));
  };
  return (
    <Card className="signup-card">
      <CardTitle>
        <Back toPage="/dashboard/auth" />
        <LoginHeader title="Create an account" />
        <AlertGroup isLiveRegion>
          {alerts.map(({ title, key }) => (
            <Alert variant="danger" title={title} key={key} />
          ))}
        </AlertGroup>
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
                <div className="password-holder">
                  {formItem.name === "password" ? (
                    <PasswordTextInput
                      isRequired={formItem.isRequired}
                      isShowPassword={showPassword}
                      id={formItem.id}
                      name={formItem.name}
                      value={userDetails[formItem.name]}
                      onChangeMethod={(val) =>
                        changeHandler(val, formItem.name)
                      }
                    />
                  ) : (
                    <TextInput
                      isRequired={formItem.isRequired}
                      type={formItem.type}
                      id={formItem.id}
                      aria-describedby="horizontal-form-name-helper"
                      name={formItem.name}
                      value={userDetails[formItem.name]}
                      onChange={(val) => changeHandler(val, formItem.name)}
                    />
                  )}
                  {formItem.name === "password" && (
                    <Button
                      variant="control"
                      onClick={onShowPassword}
                      icon={showPassword ? <EyeSlashIcon /> : <EyeIcon />}
                    ></Button>
                  )}
                </div>
                <p className="error">{errors[formItem.name]}</p>
              </FormGroup>
            );
          })}
        </Form>
      </CardBody>
      <CardFooter>
        <PasswordConstraints checkConstraints={constraints} />
        <div className="button-wrapper">
          <Button
            variant="primary"
            isBlock
            isDisabled={isSignupBtnDisabled}
            onClick={sendForRegistration}
          >
            Create Account
          </Button>
        </div>
        <NoLoginComponent />
      </CardFooter>
    </Card>
  );
};

export default SignupForm;
