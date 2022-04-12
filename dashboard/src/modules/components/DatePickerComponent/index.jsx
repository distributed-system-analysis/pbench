import React, { useState } from "react";
import {
  InputGroup,
  InputGroupText,
  DatePicker,
  isValidDate,
  yyyyMMddFormat,
  Button,
} from "@patternfly/react-core";
import moment from "moment";

function DatePickerWidget({
  dataArray,
  setPublicData,
  controllerName,
  setDateRange,
}) {
  const [fromDate, setFromDate] = useState(
    moment(new Date(1990, 10, 4)).format("YYYY/MM/DD")
  );
  const [toDate, setToDate] = useState(
    moment(new Date(2040, 10, 4)).format("YYYY/MM/DD")
  );
  const toValidator = (date) =>
    isValidDate(fromDate) && date >= fromDate
      ? ""
      : "To date must be less than from date";
  let modifiedArray = [];
  const onFromChange = (_str, date) => {
    setFromDate(new Date(date));
    moment(date).format("DD/MM/YYYY");
    if (isValidDate(date)) {
      date.setDate(date.getDate() + 1);
      setToDate(yyyyMMddFormat(date));
    } else {
      setToDate("");
    }
  };

  const filterByDate = () => {
    modifiedArray = dataArray.filter((data) => {
      let formattedData = moment(data.metadata["dataset.created"]).format(
        "YYYY/MM/DD"
      );
      return (
        Date.parse(formattedData) >= Date.parse(fromDate) &&
        Date.parse(formattedData) <= Date.parse(toDate) &&
        data.name.includes(controllerName)
      );
    });
    setPublicData(modifiedArray);
    setDateRange(fromDate, toDate);
  };
  return (
    <InputGroup style={{ marginLeft: "10px" }}>
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
