import "./index.less";

import {
  ActionGroup,
  Button,
  Card,
  CardBody,
  Form,
  FormGroup,
  Grid,
  GridItem,
  TextInput,
  Title,
} from "@patternfly/react-core";

import React from "react";
import { sendFileRequest } from "actions/relayActions";
import { useDispatch } from "react-redux";

const RelayComponent = () => {
  const [value, setValue] = React.useState("");
  const dispatch = useDispatch();
  const pullServerData = () => {
    dispatch(sendFileRequest(value));
  };
  return (
    <Grid hasGutter className="relay-ui-container">
      <Grid>
        <GridItem span={3} />
        <GridItem span={9}>
          <Title headingLevel="h3">Relay </Title>
        </GridItem>
      </Grid>

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
                  value={value}
                  onChange={(value) => setValue(value)}
                />
              </FormGroup>
              <ActionGroup>
                <Button
                  variant="primary"
                  isDisabled={!value}
                  onClick={pullServerData}
                >
                  Submit
                </Button>
              </ActionGroup>
            </Form>
          </CardBody>
        </Card>
      </div>
    </Grid>
  );
};

export default RelayComponent;
