import "./index.less";

import {
  Alert,
  AlertActionCloseButton,
  Button,
  EmptyState,
  EmptyStateBody,
  EmptyStateIcon,
  EmptyStateVariant,
  InputGroup,
  Text,
  TextContent,
  TextInput,
  TextVariants,
  Title,
} from "@patternfly/react-core";
import React, { useState } from "react";

import SearchIcon from "@patternfly/react-icons/dist/esm/icons/search-icon";
import { filterData } from "utils/filterDataset";
import { useOutletContext } from "react-router-dom";

export const LoginHint = (props) => {
  const navigate = useOutletContext();
  const { message, link, onCloseMethod, redirect } = props;
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
          onClick={() => navigate(`${redirect}`)}
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
  setDatasetName,
}) => {
  const [searchKey, setSearchKey] = useState("");

  const search = () => {
    setPublicData(filterData(dataArray, startDate, endDate, searchKey));
    setDatasetName(searchKey);
  };
  const handleKeyPress = (e) => {
    const key = e.key;
    if (key === "Enter") {
      search();
    }
  };
  return (
    <InputGroup className="searchInputGroup">
      <TextInput
        aria-label="search"
        type="text"
        placeholder="Search"
        onKeyPress={(e) => handleKeyPress(e)}
        onChange={(e) => setSearchKey(e)}
      ></TextInput>
      <Button variant="control" onClick={search} aria-label="searchButton">
        <SearchIcon />
      </Button>
    </InputGroup>
  );
};
