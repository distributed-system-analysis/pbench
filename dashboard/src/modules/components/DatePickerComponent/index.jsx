import React, { useState } from "react";
import {
  InputGroup,
  InputGroupText,
  DatePicker,
  isValidDate,
  Button,
} from "@patternfly/react-core";
import "./index.css"
import { formatDate } from "../../../utils/dateFormatter";
import { filterData } from "../../../utils/filterDataset";

function DatePickerWidget({
  dataArray,
  setPublicData,
  controllerName,
  setDateRange,
}) {
  const [fromDate, setFromDate] = useState(
    formatDate(new Date(1990,10,4))
  );
  const [toDate, setToDate] = useState(
    formatDate(new Date())
  );
  const toValidator = (date) =>
    isValidDate(fromDate) && date >= fromDate
      ? ""
      : "To date must be less than from date";

  const onFromChange = (_str, date) => {
    setFromDate(date);
    if (isValidDate(date)) {
      if(date>new Date(toDate)){
      date.setDate(date.getDate() + 1);
      setToDate(formatDate(date));
      }
    } else {
      setToDate("");
    }
  };

  const filterByDate = () => {
    let modifiedArray = filterData(dataArray,fromDate,toDate,controllerName)
    setPublicData(modifiedArray);
    setDateRange(fromDate, toDate);
  };
  return (
    <InputGroup className="filterInputGroup">
      <InputGroupText>Filter By Date</InputGroupText>
      <DatePicker
        onChange={onFromChange}
        aria-label="Start date"
        placeholder="YYYY-MM-DD"
      />
      <InputGroupText>to</InputGroupText>
      <DatePicker
        value={toDate}
        onChange={(date) => setToDate(date)}
        isDisabled={!isValidDate(fromDate)}
        rangeStart={fromDate}
        validators={[toValidator]}
        aria-label="End date"
        placeholder="YYYY-MM-DD"
      />
      <Button variant="control" onClick={filterByDate}>
        Update
      </Button>
    </InputGroup>
  );
}

export default DatePickerWidget;
