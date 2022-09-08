import "./index.less";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionToggle,
  Card,
  Grid,
  GridItem,
} from "@patternfly/react-core";
import {
  Heading,
  NewRunsHeading,
  NoExpiringRuns,
  Separator,
} from "./common-component";
import React, { useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";

import ExpiringSoonComponent from "./ExpiringSoonComponent";
import NewRunsComponent from "./NewRunsComponent";
import SavedRunsComponent from "./SavedRunsComponent";
import { getDatasets } from "actions/overviewActions";

const OverviewComponent = () => {
  const dispatch = useDispatch();
  const { endpoints } = useSelector((state) => state.apiEndpoint);
  const { loginDetails } = useSelector((state) => state.userAuth);
  const { expiringRuns } = useSelector((state) => state.overview);
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
                <NewRunsHeading />
                <NewRunsComponent />
              </AccordionContent>
            </AccordionItem>
          </GridItem>
        </Grid>
      </Accordion>
      <Separator />
      <Card className={`bordered saved-runs-container ${isExpandedClass}`}>
        <Heading title="Saved Runs" />
        <SavedRunsComponent />
      </Card>
    </div>
  );
};

export default OverviewComponent;
