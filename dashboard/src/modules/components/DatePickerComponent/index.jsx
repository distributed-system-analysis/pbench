import React, { useState } from "react";
import {
  InputGroup,
  InputGroupText,
  DatePicker,
  isValidDate,
  yyyyMMddFormat,
  Button,
} from "@patternfly/react-core";
import "./index.css"
import moment from "moment";

function DatePickerWidget({
  dataArray,
  setPublicData,
  controllerName,
  setDateRange,
}) {
  const [fromDate, setFromDate] = useState(
    moment(new Date(1990, 10, 4)).format("YYYY-MM-DD")
  );
  const [toDate, setToDate] = useState(
    moment(new Date()).format("YYYY-MM-DD")
  );
  const toValidator = (date) =>
    isValidDate(fromDate) && date >= fromDate
      ? ""
      : "To date must be less than from date";

  const onFromChange = (_str, date) => {
    setFromDate(new Date(date));
    if (isValidDate(date)) {
      if(date>new Date(toDate)){
      date.setDate(date.getDate() + 1);
      setToDate(yyyyMMddFormat(date));
      }
    } else {
      setToDate("");
    }
  };

  const filterByDate = () => {
    let modifiedArray = [];
    modifiedArray = dataArray.filter((data) => {
      return (
        new Date((data.metadata["dataset.created"]).split(":")[0])>= fromDate &&
        new Date((data.metadata["dataset.created"]).split(":")[0])<= new Date(toDate) &&
        data.name.includes(controllerName)
      );
    });
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
