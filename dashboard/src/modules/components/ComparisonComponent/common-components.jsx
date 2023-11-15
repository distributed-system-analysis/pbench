import {
  ALL_DATASETS,
  MY_DATASETS,
  PUBLIC_DATASETS,
} from "assets/constants/compareConstants";
import {
  EmptyState,
  EmptyStateBody,
  EmptyStateVariant,
  SearchInput,
  Select,
  SelectOption,
  SelectVariant,
} from "@patternfly/react-core";
import { setDatasetType, setSearchValue } from "actions/comparisonActions";
import { useDispatch, useSelector } from "react-redux";

import ChartGallery from "./ChartGallery";
import ChartModal from "./ChartModal";
import React from "react";

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

export const ViewOptions = (props) => {
  const dispatch = useDispatch();
  const [isOpen, setIsOpen] = React.useState(false);
  const selected = useSelector((state) => state.comparison.datasetType);
  const onSelect = (_event, value) => {
    console.log("selected", value);
    dispatch(setDatasetType(value, props.currPage));
    setIsOpen(false);
  };
  const onToggle = () => {
    setIsOpen(!isOpen);
  };
  const options = [
    <SelectOption key={1} value={ALL_DATASETS} />,
    <SelectOption key={2} value={MY_DATASETS} />,
    <SelectOption key={3} value={PUBLIC_DATASETS} />,
  ];
  return (
    <Select
      variant={SelectVariant.single}
      aria-label="Select Datasets Input"
      onToggle={onToggle}
      onSelect={onSelect}
      selections={selected}
      isOpen={isOpen}
      aria-labelledby={"Datasets View List"}
    >
      {options}
    </Select>
  );
};
