import { Alert, AlertActionCloseButton } from "@patternfly/react-core";
import "./index.css"
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
        <a className="alertHelpText">
          {link}
        </a>,
      ]}
    ></Alert>
  );
}

export default AlertMessage;
