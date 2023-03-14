import "./index.less";

import {
  Button,
  DatePicker,
  Split,
  SplitItem,
  isValidDate,
  yyyyMMddFormat,
} from "@patternfly/react-core";
import React, { useState } from "react";
import { applyFilter, setFilterKeys } from "actions/datasetListActions";

import { getTodayMidnightUTCDate } from "utils/dateFunctions";
import { useDispatch } from "react-redux";

const DatePickerWidget = (props) => {
  const [from, setFrom] = useState();
  const [to, setTo] = useState(getTodayMidnightUTCDate());
  const dispatch = useDispatch();

  const toValidator = (date) =>
    isValidDate(from) && date >= from
      ? ""
      : 'The "to" date must be after the "from" date';

  const fromValidator = (date) =>
    date <= getTodayMidnightUTCDate()
      ? ""
      : "The Uploaded date cannot be in the future!";

  const onFromChange = (_str, date) => {
    setFrom(new Date(date));
  };

  const onToChange = (_str, date) => {
    if (isValidDate(date)) {
      setTo(yyyyMMddFormat(date));
    }
  };

  const filterByDate = () => {
    if (from) {
      dispatch(setFilterKeys(from, new Date(to)));
      dispatch(applyFilter());
      props.setPage(1);
    }
  };

  return (
    <>
      <Split>
        <SplitItem style={{ padding: "6px 12px 0 12px" }}>
          Filter by date
        </SplitItem>
        <SplitItem>
          <DatePicker
            onChange={onFromChange}
            aria-label="Start date"
            placeholder="YYYY-MM-DD"
            validators={[fromValidator]}
          />
        </SplitItem>
        <SplitItem style={{ padding: "6px 12px 0 12px" }}>to</SplitItem>
        <SplitItem>
          <DatePicker
            value={yyyyMMddFormat(to)}
            onChange={onToChange}
            isDisabled={!isValidDate(from)}
            rangeStart={from}
            validators={[toValidator]}
            aria-label="End date"
            placeholder="YYYY-MM-DD"
          />
        </SplitItem>
        <Button variant="control" onClick={filterByDate}>
          Update
        </Button>
      </Split>
    </>
  );
};

export default DatePickerWidget;
