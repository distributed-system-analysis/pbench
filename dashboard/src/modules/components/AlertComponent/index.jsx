import { Alert, AlertActionCloseButton } from "@patternfly/react-core";
import { useNavigate } from "react-router-dom";
import "./index.css";
import React from "react";
import { AUTH_LOGIN } from "utils/routeConstants";

function LoginAlertMessage({ message, link }) {
  const navigate = useNavigate();
  return (
    <Alert
      className="alertNotification"
      variant="info"
      isInline
      actionClose={
        <AlertActionCloseButton
          onClose={() =>
            (document.querySelector(".alertNotification").style.display =
              "none")
          }
        />
      }
      title={[
        'Want to see your own data?',
        <a className="alertHelpText" onClick={() => navigate(`/${AUTH_LOGIN}`)}>
          Login to your account
        </a>,
      ]}
    ></Alert>
  );
}

export default LoginAlertMessage;
