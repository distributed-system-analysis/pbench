import React from "react";
import { Alert, 
    AlertGroup, 
    AlertVariant,
    AlertActionCloseButton 
} from '@patternfly/react-core';
import { useDispatch, useSelector } from "react-redux";
import { CLEAR_TOAST } from "actions/types";

const ToastComponent = () => {

    const { alerts } = useSelector((state) => state.toastReducer)
    const dispatch = useDispatch();
    
    const removeToast = (key) => {
        dispatch({ type: CLEAR_TOAST, payload:key })
    }
    return (
        <AlertGroup isToast>
          {
            alerts.map(item => {
              return(
                <Alert
              variant={AlertVariant[item.variant]}
              title={item.title}
              key={item.key}
              timeout={true}
              onTimeout={() => removeToast()}
              actionClose={
                <AlertActionCloseButton
                  title={item.title}
                  variantLabel={`${item.variant} alert`}
                  onClose={() => removeToast(item.key)}
                />
              }
            >
              {
                item?.message && 
                <p>{item?.message}</p>
              }
            </Alert>
              )
            })
          }
            
        </AlertGroup>
    )
}

export default ToastComponent;
