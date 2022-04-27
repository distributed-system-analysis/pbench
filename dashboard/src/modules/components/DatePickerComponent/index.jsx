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
  const [fromDate, setFromDate] = useState({});
  const [toDate, setToDate] = useState(new Date());
  const toValidator = (date) =>
    date >= fromDate
      ? ""
      : "To date must be greater than or equal to from date";

  const onFromChange = (_str, date) => {
    setFromDate(date);
    if (isValidDate(date)) {
      if (date > toDate) {
        date.setDate(date.getDate() + 1);
        setToDate(date);
      }
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
        value={formatDate(toDate)}
        onChange={(_str,date) => setToDate(date)}
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
