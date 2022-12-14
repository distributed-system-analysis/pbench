import "./index.less";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionToggle,
  Card,
  Grid,
  GridItem,
  Spinner,
} from "@patternfly/react-core";
import {
  Heading,
  NewRunsHeading,
  NoExpiringRuns,
  Separator,
} from "./common-component";
import React, { useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";

import { EmptyTable } from "../TableComponent/common-components";
import ExpiringSoonComponent from "./ExpiringSoonComponent";
import NewRunsComponent from "./NewRunsComponent";
import SavedRunsComponent from "./SavedRunsComponent";
import { getDatasets } from "actions/overviewActions";

const OverviewComponent = () => {
  const dispatch = useDispatch();
  const { endpoints } = useSelector((state) => state.apiEndpoint);
  const { loginDetails } = useSelector((state) => state.userAuth);
  const { expiringRuns, savedRuns, newRuns, loadingDone } = useSelector(
    (state) => state.overview
  );
  const [expanded, setExpanded] = React.useState(
    new Set(["expired", "newRuns"])
  );
  useEffect(() => {
    if (Object.keys(endpoints).length > 0) {
      dispatch(getDatasets());
    }
  }, [dispatch, endpoints, loginDetails]);

  const onToggle = (id) => {
    if (expanded.has(id)) {
      expanded.delete(id);
    } else {
      expanded.add(id);
    }
    setExpanded(new Set(expanded));
  };
  const isExpandedClass = expanded.size === 0 ? "not-expanded" : "";
  return (
    <div className="overview-container">
      {!loadingDone ? (
        <div className="dashboard-loading-container">
          <Spinner isSVG />
          <h2 className="heading-h2">Preparing dashboard</h2>

          <p>If page doesn`t load, try refreshing it or retrying later.</p>
        </div>
      ) : (
        <>
          <Heading title="Overview" />
          <Accordion isBordered>
            <Grid hasGutter>
              <GridItem span={4}>
                <AccordionItem>
                  <AccordionToggle
                    onClick={() => {
                      onToggle("expired");
                    }}
                    isExpanded={expanded.has("expired")}
                    id="expired"
                  >
                    Expiring soon
                  </AccordionToggle>
                  <AccordionContent isHidden={!expanded.has("expired")}>
                    {expiringRuns.length > 0 ? (
                      <ExpiringSoonComponent />
                    ) : (
                      <NoExpiringRuns />
                    )}
                  </AccordionContent>
                </AccordionItem>
              </GridItem>
              <GridItem span={8} className="new-runs-container ">
                <AccordionItem>
                  <AccordionToggle
                    onClick={() => {
                      onToggle("newRuns");
                    }}
                    isExpanded={expanded.has("newRuns")}
                    id="newRuns"
                  >
                    New and Unmanaged
                  </AccordionToggle>
                  <AccordionContent isHidden={!expanded.has("newRuns")}>
                    {newRuns.length > 0 ? (
                      <>
                        <NewRunsHeading />
                        <NewRunsComponent />
                      </>
                    ) : (
                      <EmptyTable />
                    )}
                  </AccordionContent>
                </AccordionItem>
              </GridItem>
            </Grid>
          </Accordion>
          <Separator />
          <Card className={`bordered saved-runs-container ${isExpandedClass}`}>
            <Heading title="Saved Runs" />
            {savedRuns.length > 0 ? <SavedRunsComponent /> : <EmptyTable />}
          </Card>
        </>
      )}
    </div>
  );
};

export default OverviewComponent;
