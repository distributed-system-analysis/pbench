import { Alert } from "@patternfly/react-core";
import React from "react";

const AlertMessage = (message) => {
  return (
    <Alert
      className="alertNotification"
      variant="info"
      isInline
      title={message}
    />
  );
};

export default AlertMessage;
