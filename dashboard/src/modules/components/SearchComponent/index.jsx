import React from "react";
import { InputGroup, TextInput, Button } from "@patternfly/react-core";
import SearchIcon from "@patternfly/react-icons/dist/esm/icons/search-icon";
import { useState } from "react";
import moment from "moment";
function SearchBox({
  dataArray,
  setPublicData,
  startDate,
  endDate,
  setControllerName,
}) {
  const [controllerValue, setControllerValue] = useState("");
  let modifiedArray = [];
  const searchController = () => {
    modifiedArray = dataArray.filter((data) => {
      let formattedData = moment(data.metadata["dataset.created"]).format(
        "YYYY/MM/DD"
      );
      return (
        data.controller.includes(controllerValue) &&
        Date.parse(formattedData) >= Date.parse(startDate) &&
        Date.parse(formattedData) <= Date.parse(endDate)
      );
    });
    setPublicData(modifiedArray);
    setControllerName(controllerValue);
  };
  return (
    <InputGroup style={{ width: "18vw" }}>
      <TextInput
        type="text"
        placeholder="Search Controllers"
        style={{ width: 20 }}
        onChange={(e) => setControllerValue(e)}
      ></TextInput>
      <Button variant="control" onClick={searchController}>
        <SearchIcon />
      </Button>
    </InputGroup>
  );
}

export default SearchBox;
