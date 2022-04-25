import {
  Alert,
  AlertActionCloseButton,
  Button,
  EmptyState,
  EmptyStateVariant,
  EmptyStateIcon,
  Title,
  EmptyStateBody,
  TextContent,
  TextVariants,
  Text,
  InputGroup,
  TextInput,
} from "@patternfly/react-core";
import SearchIcon from "@patternfly/react-icons/dist/esm/icons/search-icon";
import "./index.less";
import React, { useState } from "react";

export const LoginHint = (props) => {
  const { message, link, onCloseMethod } = props;
  return (
    <Alert
      className="alertNotification"
      variant="info"
      isInline
      actionClose={<AlertActionCloseButton onClose={onCloseMethod} />}
      title={[
        message,
        <Button
          variant="link"
          key="login-hint-button"
          className="alertHelpText"
        >
          {link}
        </Button>,
      ]}
    />
  );
};

export const EmptyTable = () => {
  return (
    <EmptyState variant={EmptyStateVariant.small}>
      <EmptyStateIcon icon={SearchIcon} />
      <Title headingLevel="h2" size="lg">
        No results found
      </Title>
      <EmptyStateBody>No Records Available</EmptyStateBody>
    </EmptyState>
  );
};

export const Heading = (props) => {
  const { headingTitle, containerClass } = props;
  return (
    <TextContent className={containerClass}>
      <Text component={TextVariants.h2}>{headingTitle}</Text>
    </TextContent>
  );
};

export const SearchBox = ({
  dataArray,
  setPublicData,
  startDate,
  endDate,
  setControllerName,
})=> {
  const [controllerValue, setControllerValue] = useState("");
  const searchController = () => {
    let modifiedArray = [];
    modifiedArray = dataArray.filter((data) => {
      return (
        data.controller.includes(controllerValue) &&
        new Date(data.metadata["dataset.created"].split(":")[0]) >= startDate &&
        new Date(data.metadata["dataset.created"].split(":")[0]) <=
          new Date(endDate)
      );
    });
    setPublicData(modifiedArray);
    setControllerName(controllerValue);
  };
  return (
    <InputGroup className="searchInputGroup">
      <TextInput
        id="tableSearch"
        type="text"
        placeholder="Search Controllers"
        onChange={(e) => setControllerValue(e)}
      ></TextInput>
      <Button variant="control" onClick={searchController}>
        <SearchIcon />
      </Button>
    </InputGroup>
  );
}
