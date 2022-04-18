import React,{useState} from "react";
import "./index.css"
import { InputGroup, TextInput, Button } from "@patternfly/react-core";
import SearchIcon from "@patternfly/react-icons/dist/esm/icons/search-icon";
function SearchBox({
  dataArray,
  setPublicData,
  startDate,
  endDate,
  setControllerName,
}) {
  const [controllerValue, setControllerValue] = useState("");
  const searchController = () => {
    let modifiedArray = [];
    modifiedArray = dataArray.filter((data) => {
      return (
        data.controller.includes(controllerValue) &&
          new Date((data.metadata["dataset.created"]).split(":")[0])>= startDate &&
          new Date((data.metadata["dataset.created"]).split(":")[0])<= new Date(endDate)
      );
    });
    setPublicData(modifiedArray);
    setControllerName(controllerValue);
  };
  return (
    <InputGroup className="searchInputGroup">
      <TextInput
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

export default SearchBox;
