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
import bumpToDate from "utils/bumpDate";

function DatePickerWidget({
  dataArray,
  setPublicData,
  controllerName,
  setDateRange,
}) {
  const [fromDate, setFromDate] = useState({});
  const [toDate, setToDate] = useState(
    bumpToDate(constructUTCDate(formatDate(new Date())), 1)
  );
  const [strDate, setStrDate] = useState(
    new Date().toLocaleDateString("fr-CA")
  );
  const toValidator = (date) =>
    date >= fromDate
      ? ""
      : "To date must be greater than or equal to from date";

  const onFromChange = (_str, date) => {
    const selectedDate = constructUTCDate(_str);
    setFromDate(isValidDate(date) ? selectedDate : {});
    if (isValidDate(date)) {
      if (date > new Date(strDate)) {
        setToDate(bumpToDate(constructUTCDate(formatDate(new Date(_str))), 1));
        setStrDate(_str);
      }
    }
  };

  const filterByDate = () => {
    setPublicData(filterData(dataArray, fromDate, toDate, controllerName));
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
          setToDate(
            bumpToDate(constructUTCDate(formatDate(new Date(_str))), 1)
          );
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
