import React from "react";
import { InputGroup, TextInput } from "@patternfly/react-core";
import "./index.less";

const filterTOC = (dataArray, searchKey) => {
  const x = dataArray.filter((data) => {
    return data.name.includes(searchKey);
  });
  return x;
};

export const SearchTOC = ({ dataArray, setTableData}) => {
  const search = (searchKey) => {
    setTableData(filterTOC(dataArray, searchKey));
  };
  return (
    <InputGroup className="searchInputGroup">
      <TextInput
        aria-label="search"
        type="text"
        placeholder="Search"
        onChange={(e) => search(e)}
      ></TextInput>
    </InputGroup>
  );
};
