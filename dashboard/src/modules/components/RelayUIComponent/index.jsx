import "./index.less";

import {
  ActionGroup,
  Button,
  Card,
  CardBody,
  Form,
  FormGroup,
  Modal,
  ModalVariant,
  TextInput,
} from "@patternfly/react-core";
import {
  handleInputChange,
  toggleRelayModal,
  uploadFile,
} from "actions/relayActions";
import { useDispatch, useSelector } from "react-redux";

import React from "react";

const RelayComponent = () => {
  const { isRelayModalOpen, relayInput } = useSelector(
    (state) => state.overview
  );
  const dispatch = useDispatch();
  const pullServerData = () => {
    dispatch(uploadFile());
  };
  const handleClose = () => {
    dispatch(handleInputChange(""));
    dispatch(toggleRelayModal(false));
  };
  return (
    <Modal
      className="relay-ui-container"
      title="Relay"
      variant={ModalVariant.small}
      isOpen={isRelayModalOpen}
      onClose={handleClose}
    >
      {/* Need to update the about content */}
      <div>To pull the dataset</div>
      <div className="card-wrapper">
        <Card>
          <CardBody>
            <Form>
              <FormGroup
                label="Enter the Relay URI"
                isRequired
                fieldId="relay-uri"
              >
                <TextInput
                  isRequired
                  type="text"
                  id="relay-uri"
                  name="relay-uri"
                  value={relayInput}
                  onChange={(value) => dispatch(handleInputChange(value))}
                />
              </FormGroup>
              <ActionGroup>
                <Button
                  variant="primary"
                  isDisabled={!relayInput}
                  onClick={pullServerData}
                >
                  Submit
                </Button>
              </ActionGroup>
            </Form>
          </CardBody>
        </Card>
      </div>
    </Modal>
  );
};

export default RelayComponent;
