import { Button, Card, CardBody } from "@patternfly/react-core";
import React, { useEffect } from "react";
import {
  getAPIkeysList,
  setNewKeyLabel,
  toggleNewAPIKeyModal,
} from "actions/keyManagementActions";
import { useDispatch, useSelector } from "react-redux";

import KeyListTable from "./KeyListTable";
import NewKeyModal from "./NewKeyModal";

const KeyManagementComponent = () => {
  const dispatch = useDispatch();
  const isModalOpen = useSelector((state) => state.keyManagement.isModalOpen);
  const { idToken } = useSelector((state) => state.apiEndpoint?.keycloak);
  useEffect(() => {
    if (idToken) {
      dispatch(getAPIkeysList);
    }
  }, [dispatch, idToken]);
  const handleModalToggle = () => {
    dispatch(setNewKeyLabel(""));
    dispatch(toggleNewAPIKeyModal(!isModalOpen));
  };
  return (
    <Card className="key-management-container">
      <CardBody>
        <div className="heading-wrapper">
          <p className="heading-title">API Keys</p>
          <Button variant="tertiary" onClick={handleModalToggle}>
            New API key
          </Button>
        </div>
        <p className="key-desc">
          This is a list of API keys associated with your account. Remove any
          keys that you do not recognize.
        </p>
        <KeyListTable />
      </CardBody>
      <NewKeyModal handleModalToggle={handleModalToggle} />
    </Card>
  );
};

export default KeyManagementComponent;
