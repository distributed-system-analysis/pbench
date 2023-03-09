import {
  EmptyState,
  EmptyStateBody,
  EmptyStateVariant,
  SearchInput,
} from "@patternfly/react-core";
import { useDispatch, useSelector } from "react-redux";

import ChartGallery from "./ChartGallery";
import ChartModal from "./ChartModal";
import React from "react";
import { setSearchValue } from "actions/comparisonActions";

export const UnsupportedTextComponent = (props) => (
  <EmptyState variant={EmptyStateVariant.xs}>
    <div>{props.title}</div>
    <EmptyStateBody>{props.message}</EmptyStateBody>
  </EmptyState>
);

export const MainContent = () => {
  const {
    isCompareSwitchChecked,
    compareChartData,
    chartData,
    unsupportedType,
    unmatchedMessage,
    activeChart,
  } = useSelector((state) => state.comparison);

  const message = isCompareSwitchChecked
    ? "Benchmarks are of non-compatabile types!"
    : "Benchmark type is currently unsupported!";
  const data = isCompareSwitchChecked ? compareChartData : chartData;
  return (
    <>
      {isCompareSwitchChecked ? (
        unmatchedMessage ? (
          <UnsupportedTextComponent
            message={message}
            title={unmatchedMessage}
          />
        ) : (
          <ChartGallery dataToPlot={data} />
        )
      ) : unsupportedType ? (
        <UnsupportedTextComponent message={message} title={unsupportedType} />
      ) : (
        <ChartGallery dataToPlot={data} />
      )}
      {activeChart && <ChartModal dataToPlot={data} />}
    </>
  );
};

export const SearchByName = () => {
  const dispatch = useDispatch();
  const onSearchChange = (value) => {
    dispatch(setSearchValue(value));
  };
  const { searchValue } = useSelector((state) => state.comparison);
  return (
    <SearchInput
      placeholder="Search by name"
      value={searchValue}
      onChange={(_event, value) => onSearchChange(value)}
    />
  );
};
