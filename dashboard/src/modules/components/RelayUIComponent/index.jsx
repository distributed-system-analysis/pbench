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
  Popover,
  TextInput,
  Title,
} from "@patternfly/react-core";
import {
  handleInputChange,
  setRelayModalState,
  uploadFile,
} from "actions/relayActions";
import { useDispatch, useSelector } from "react-redux";

import { OutlinedQuestionCircleIcon } from "@patternfly/react-icons";
import React from "react";

const AboutComponent = () => (
  <div className="about-container">
    <p>
      The Pbench Agent can push datasets to a Pbench Server directly, when the
      server is accessible from the system where the Pbench Agent is being used.
    </p>
    <p>
      When a firewall prevents this direct access, the Pbench Agent can store a
      dataset tarball and a manifest file on a file relay server which can be
      reached by both the Pbench Agent and the Pbench Server.
    </p>
    <p>
      Enter the relay server URI reported by the Pbench Agent and press Submit
      to begin the upload.
    </p>
  </div>
);
const PopoverComponent = () => (
  <Popover
    aria-label="Relay About Popover"
    headerContent={<div>About</div>}
    bodyContent={<AboutComponent />}
    maxWidth="4vw"
  >
    <Button variant="plain" aria-label="About" className="popover-btn">
      <OutlinedQuestionCircleIcon />
    </Button>
  </Popover>
);

const RelayComponent = () => {
  const { isRelayModalOpen, relayInput } = useSelector(
    (state) => state.overview
  );
  const dispatch = useDispatch();

  const handleClose = () => {
    dispatch(handleInputChange(""));
    dispatch(setRelayModalState(false));
  };

  return (
    <Modal
      className="relay-ui-container"
      aria-label="Relay"
      variant={ModalVariant.small}
      isOpen={isRelayModalOpen}
      onClose={handleClose}
    >
      <div className="modal-heading">
        <Title headingLevel="h3">Pull Datasets</Title>
        <PopoverComponent />
      </div>
      <p className="modal-desc">
        When you use the Pbench Agent{" "}
        <span className="italicized"> pbench-results-move </span> command with
        the
        <span className="italicized"> --relay </span>option to push results to a
        relay server, the command will report a URL.
      </p>
      <p className="modal-desc">
        Enter that URL here to instruct the Pbench Server to upload the results
        data from the relay and remove it from the relay.
      </p>

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
                  onClick={() => dispatch(uploadFile())}
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
