import "./index.less";

import * as CONSTANTS from "assets/constants/browsingPageConstants";

import {
  Button,
  DatePicker,
  Split,
  SplitItem,
  isValidDate,
} from "@patternfly/react-core";
import React, { useState } from "react";
import { applyFilter, setFilterKeys } from "actions/datasetListActions";
import { useDispatch, useSelector } from "react-redux";

import { getTodayMidnightUTCDate } from "utils/dateFunctions";

const DatePickerWidget = (props) => {
  const dispatch = useDispatch();
  const { filter } = useSelector((state) => state.datasetlist);

  const [isEndDateError, setIsEndDateError] = useState(false);

  const fromValidator = (date) =>
    date <= getTodayMidnightUTCDate()
      ? ""
      : "The Uploaded date cannot be in the future!";

  const toValidator = (date) =>
    isValidDate(filter.startDate) && date >= filter.startDate
      ? ""
      : 'The "to" date must be after the "from" date';

  const onFromChange = (_str, date) => {
    dispatch(setFilterKeys(new Date(date), filter.endDate));
    if (filter.endDate) {
      checkEndDate(date, filter.endDate);
    }
  };

  const onToChange = (_str, date) => {
    if (isValidDate(new Date(date))) {
      dispatch(setFilterKeys(filter.startDate, new Date(date)));
    }
    checkEndDate(filter.startDate, date);
  };
  const checkEndDate = (fromDate, toDate) => {
    new Date(fromDate) >= new Date(toDate)
      ? setIsEndDateError(true)
      : setIsEndDateError(false);
  };
  const filterByDate = () => {
    if (filter.startDate) {
      dispatch(applyFilter());
      props.setPage(CONSTANTS.START_PAGE_NUMBER);
    }
  };

  return (
    <>
      <Split className="browsing-page-date-picker">
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
            onChange={onToChange}
            isDisabled={!isValidDate(filter.startDate)}
            rangeStart={filter.startDate}
            validators={[toValidator]}
            aria-label="End date"
            placeholder="YYYY-MM-DD"
            helperText={
              isEndDateError && `The "to" date must be after the "from" date`
            }
          />
        </SplitItem>
        <Button
          variant="control"
          onClick={filterByDate}
          className="filter-btn"
          isDisabled={isEndDateError}
        >
          Update
        </Button>
      </Split>
    </>
  );
};

export default DatePickerWidget;
