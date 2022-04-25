import React,{useState} from "react";
import { InputGroup, TextInput, Button } from "@patternfly/react-core";
import SearchIcon from "@patternfly/react-icons/dist/esm/icons/search-icon";
import { filterData } from "utils/filterDataset";
function SearchBox({
  dataArray,
  setPublicData,
  startDate,
  endDate,
  setControllerName,
}) {
  const [controllerValue, setControllerValue] = useState("");
  const searchController = () => {
    setPublicData(filterData(dataArray, startDate, endDate, controllerValue));
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
