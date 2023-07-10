import "./index.less";

import {
  Divider,
  Flex,
  FlexItem,
  Sidebar,
  SidebarContent,
  SidebarPanel,
} from "@patternfly/react-core";
import React, { useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";

import ChartGallery from "./ChartGallery";
import PanelConent from "./PanelContent";
import { getDatasets } from "actions/overviewActions";
import { getQuisbyData } from "actions/quisbyChartActions";
import { useNavigate } from "react-router-dom";

const QuisbyChartsComponent = () => {
  const dispatch = useDispatch();
  const navigate = useNavigate();

  const { datasets } = useSelector((state) => state.overview);

  useEffect(() => {
    if (Array.isArray(datasets) && datasets.length > 0) {
      dispatch(getQuisbyData(datasets[0]));
    } else {
      dispatch(getDatasets());
    }
  }, [datasets, dispatch, navigate]);
  return (
    <div className="chart-container">
      <Flex className="heading-container">
        <FlexItem className="heading">Data comparison</FlexItem>
      </Flex>
      <Divider component="div" className="header-separator" />
      <Sidebar>
        <SidebarPanel>
          <div className="heading">Datasets</div>
          <PanelConent />
        </SidebarPanel>
        <SidebarContent>
          <div className="heading">Results</div>
          <ChartGallery />
        </SidebarContent>
      </Sidebar>
    </div>
  );
};

export default QuisbyChartsComponent;
