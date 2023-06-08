import "./index.less";

import {
  Button,
  Card,
  CardBody,
  CardFooter,
  CardTitle,
  Flex,
  FlexItem,
  Grid,
  GridItem,
  TextInput,
  Title,
} from "@patternfly/react-core";

import DatasetTable from "./DatasetsTable";
import React from "react";

const RelayComponent = () => {
  const [value, setValue] = React.useState("");
  return (
    <Grid hasGutter className="relay-ui-container">
      <Grid>
        <GridItem span={1} />
        <GridItem span={10}>
          <Title headingLevel="h3">Relay </Title>
        </GridItem>
      </Grid>
      <GridItem span={1} />
      <GridItem span={10}>
        <Card>
          <CardBody>
            <Title headingLevel="h4">Relay Datasets</Title>
            <DatasetTable />
          </CardBody>
        </Card>
        <div className="divider" />
        <Card>
          <CardBody>
            <Title headingLevel="h4">Pull Datasets</Title>
            <Flex>
              <FlexItem>Enter the Relay URI</FlexItem>
              <FlexItem flex={{ default: "flex_3" }}>
                <TextInput
                  type="text"
                  value={value}
                  onChange={(value) => setValue(value)}
                  aria-label="Relay URI"
                  placeholder="Relay URI"
                />
              </FlexItem>
              <FlexItem flex={{ default: "flex_1" }}>
                <Button isDisabled={!value}>Submit</Button>
              </FlexItem>
            </Flex>
          </CardBody>
        </Card>
      </GridItem>
      <GridItem span={1} />
    </Grid>
  );
};

export default RelayComponent;
