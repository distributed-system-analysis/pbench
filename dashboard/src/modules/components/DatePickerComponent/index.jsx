import React, { useState } from "react";
import {
  InputGroup,
  InputGroupText,
  DatePicker,
  isValidDate,
  Button,
} from "@patternfly/react-core";
import "./index.css";
import { formatDate } from "../../../utils/dateFormatter";
import { filterData } from "../../../utils/filterDataset";
import { constructUTCDate } from "../../../utils/constructDate";

function DatePickerWidget({
  dataArray,
  setPublicData,
  controllerName,
  setDateRange,
}) {
  const [fromDate, setFromDate] = useState({});
  const [toDate, setToDate] = useState(
    constructUTCDate(new Date(formatDate(new Date())))
  );
  const [strDate, setStrDate] = useState(formatDate(new Date()));
  const toValidator = (date) =>
    date >= fromDate
      ? ""
      : "To date must be greater than or equal to from date";

  const onFromChange = (_str, date) => {
    setFromDate(constructUTCDate(new Date(_str)));
    if (isValidDate(date)) {
      if (date > toDate) {
        let selectedDate = new Date(_str);
        selectedDate.setDate(selectedDate.getDate() + 1);
        setToDate(constructUTCDate(selectedDate));
        setStrDate(formatDate(selectedDate));
      }
    }
  };

  const filterByDate = () => {
    let modifiedArray = filterData(dataArray, fromDate, toDate, controllerName);
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
        value={strDate}
        onChange={(_str, date) => {
          setStrDate(_str);
          setToDate(constructUTCDate(new Date(_str)));
        }}
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
