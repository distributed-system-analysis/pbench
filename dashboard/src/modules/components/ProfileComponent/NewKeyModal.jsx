import "./index.less";

import { Button, Modal, ModalVariant, TextInput } from "@patternfly/react-core";
import {
  sendNewKeyRequest,
  setNewKeyLabel,
} from "actions/keyManagementActions";
import { useDispatch, useSelector } from "react-redux";

import React from "react";

const NewKeyModal = (props) => {
  const dispatch = useDispatch();
  const { isModalOpen, newKeyLabel } = useSelector(
    (state) => state.keyManagement
  );
  const handleKeyPress = (e) => {
    const key = e.key;
    if (key === "Enter") {
      newKeyRequest();
    }
  };
  const newKeyRequest = () => {
    dispatch(sendNewKeyRequest(newKeyLabel));
  };
  return (
    <Modal
      variant={ModalVariant.small}
      title="New API Key"
      isOpen={isModalOpen}
      showClose={false}
      actions={[
        <Button
          key="create"
          variant="primary"
          form="modal-with-form-form"
          onClick={() => newKeyRequest()}
        >
          Create
        </Button>,
        <Button key="cancel" variant="link" onClick={props.handleModalToggle}>
          Cancel
        </Button>,
      ]}
    >
      <div id="new-api-key-form">
        <div label="Enter the label" id="new-api-key-form-label">
          Enter the label
        </div>
        <TextInput
          type="text"
          id="new-api-key-form"
          name="new-api-key-form"
          value={newKeyLabel}
          onKeyPress={(e) => handleKeyPress(e)}
          onChange={(value) => dispatch(setNewKeyLabel(value))}
        />
      </div>
    </Modal>
  );
};

export default NewKeyModal;
