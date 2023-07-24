import "./index.less";

import {
  Button,
  Divider,
  Flex,
  FlexItem,
  Sidebar,
  SidebarContent,
  SidebarPanel,
  Switch,
} from "@patternfly/react-core";
import { MainContent, SearchByName } from "./common-components";
import React, { useEffect } from "react";
import {
  compareMultipleDatasets,
  getQuisbyData,
  toggleCompareSwitch,
} from "actions/comparisonActions";
import { useDispatch, useSelector } from "react-redux";

import PanelConent from "./PanelContent";
import { getDatasets } from "actions/overviewActions";
import { useNavigate } from "react-router-dom";

const ComparisonComponent = () => {
  const dispatch = useDispatch();
  const navigate = useNavigate();

  const { datasets } = useSelector((state) => state.overview);
  const { isCompareSwitchChecked, selectedResourceIds } = useSelector(
    (state) => state.comparison
  );
  useEffect(() => {
    if (datasets && datasets.length > 0) {
      dispatch(getQuisbyData(datasets[0]));
    } else {
      dispatch(getDatasets());
    }
  }, [datasets, dispatch, navigate]);
  return (
    <div className="chart-container">
      <Flex className="heading-container">
        <FlexItem className="heading">Data Visualization</FlexItem>
      </Flex>
      <Divider component="div" className="header-separator" />
      <Sidebar>
        <SidebarPanel>
          <div className="sidepanel-heading-container">
            <div className="heading">Datasets</div>
            <div className="compare-switch">
              <Switch
                id="simple-switch"
                label="Compare"
                isChecked={isCompareSwitchChecked}
                onChange={() => dispatch(toggleCompareSwitch())}
              />
            </div>
          </div>
          {isCompareSwitchChecked && (
            <Button
              isBlock
              variant="primary"
              isDisabled={selectedResourceIds.length < 2}
              onClick={() => dispatch(compareMultipleDatasets())}
            >
              Compare Datasets
            </Button>
          )}
          <SearchByName />
          <PanelConent />
        </SidebarPanel>
        <SidebarContent>
          <div className="heading">Results</div>
          <MainContent />
        </SidebarContent>
      </Sidebar>
    </div>
  );
};

export default ComparisonComponent;
