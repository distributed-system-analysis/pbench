import "./index.less";

import { Grid, GridItem } from "@patternfly/react-core";
import {
  Heading,
  NewRunsHeading,
  NoExpiringRuns,
  Separator,
} from "./common-component";
import React, { useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";

import NewRunsComponent from "./NewRunsComponent";
import { getDatasets } from "actions/overviewActions";

const OverviewComponent = () => {
  const dispatch = useDispatch();
  const { endpoints } = useSelector((state) => state.apiEndpoint);
  const { loginDetails } = useSelector((state) => state.userAuth);

  useEffect(() => {
    if (Object.keys(endpoints).length > 0) {
      dispatch(getDatasets());
    }
  }, [dispatch, endpoints, loginDetails]);

  return (
    <div className="overview-container">
      <Heading title="Overview" />
      <Grid hasGutter>
        <GridItem
          className="bordered expiring-container"
          span={4}
          rowSpan={6}
          lgRowSpan={6}
          xlRowSpan={7}
        >
          <Heading title="Expiring soon" />
          <NoExpiringRuns />
        </GridItem>
        <GridItem
          className="bordered new-runs-container"
          span={8}
          rowSpan={6}
          lgRowSpan={6}
          xlRowSpan={7}
        >
          <NewRunsHeading />
          <NewRunsComponent />
        </GridItem>
      </Grid>
      <Separator />
      <div className="bordered saved-runs-container">
        <Heading title="Saved Runs" />
      </div>
    </div>
  );
};

export default OverviewComponent;
