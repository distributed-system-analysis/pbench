import { Alert, AlertActionCloseButton } from "@patternfly/react-core";
import React from "react";

function AlertMessage({ message, link }) {
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
        `${message}`,
        <a style={{ fontSize: "smaller", marginLeft: "10px" }}>
          Login to create an account
        </a>,
      ]}
    ></Alert>
  );
}

export default AlertMessage;
