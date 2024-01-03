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
import { MainContent, SearchByName, ViewOptions } from "./common-components";
import React, { useEffect } from "react";
import {
  compareMultipleDatasets,
  getQuisbyData,
  resetList,
  toggleCompareSwitch,
} from "actions/comparisonActions";
import { useDispatch, useSelector } from "react-redux";

import Cookies from "js-cookie";
import PanelConent from "./PanelContent";

const ComparisonComponent = () => {
  const dispatch = useDispatch();
  const loggedIn = Cookies.get("isLoggedIn");

  const { datasets } = useSelector((state) => state.overview);
  const { isCompareSwitchChecked, selectedResourceIds } = useSelector(
    (state) => state.comparison
  );
  useEffect(() => {
    if (datasets && datasets.length > 0) {
      dispatch(getQuisbyData(datasets[0]));
    } else {
      resetList(dispatch);
    }
  }, [datasets, dispatch]);
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
          {loggedIn && <ViewOptions />}

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
