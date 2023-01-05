import {
  Alert,
  AlertActionCloseButton,
  AlertGroup,
  AlertVariant,
} from "@patternfly/react-core";
import { useDispatch, useSelector } from "react-redux";

import React from "react";
import { hideToast } from "actions/toastActions";

const ToastComponent = () => {
  const { alerts } = useSelector((state) => state.toastReducer);
  const dispatch = useDispatch();

  const removeToast = (key) => {
    dispatch(hideToast(key));
  };
  return (
    <AlertGroup isToast>
      {alerts.map((item) => (
        <Alert
          variant={AlertVariant[item.variant]}
          title={item.title}
          key={item.key}
          timeout={true}
          onTimeout={() => removeToast(item.key)}
          actionClose={
            <AlertActionCloseButton
              title={item.title}
              variantLabel={`${item.variant} alert`}
              onClose={() => removeToast(item.key)}
            />
          }
        >
          {item?.message && <p>{item?.message}</p>}
        </Alert>
      ))}
    </AlertGroup>
  );
};

export default ToastComponent;
