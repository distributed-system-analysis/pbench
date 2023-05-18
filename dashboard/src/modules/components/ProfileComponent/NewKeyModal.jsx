import "./index.less";

import {
  Button,
  Form,
  FormGroup,
  Modal,
  ModalVariant,
  TextInput,
} from "@patternfly/react-core";
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
          onClick={() => dispatch(sendNewKeyRequest(newKeyLabel))}
        >
          Create
        </Button>,
        <Button key="cancel" variant="link" onClick={props.handleModalToggle}>
          Cancel
        </Button>,
      ]}
    >
      <Form id="new-api-key-form">
        <FormGroup label="Enter the label" fieldId="new-api-key-form">
          <TextInput
            type="text"
            id="new-api-key-form"
            name="new-api-key-form"
            value={newKeyLabel}
            onChange={(value) => dispatch(setNewKeyLabel(value))}
          />
        </FormGroup>
      </Form>
    </Modal>
  );
};

export default NewKeyModal;
