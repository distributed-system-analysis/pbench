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

import NewRunsComponent from "./NewRunsComponent";
import SavedRunsComponent from "./SavedRunsComponent";
import { getDatasets } from "actions/overviewActions";

const OverviewComponent = () => {
  const dispatch = useDispatch();
  const { endpoints } = useSelector((state) => state.apiEndpoint);
  const { loginDetails } = useSelector((state) => state.userAuth);
  const [expanded, setExpanded] = React.useState(["expired", "newRuns"]);

  useEffect(() => {
    if (Object.keys(endpoints).length > 0) {
      dispatch(getDatasets());
    }
  }, [dispatch, endpoints, loginDetails]);

  const onToggle = (id) => {
    if (expanded.includes(id)) {
      setExpanded(expanded.filter((item) => item !== id));
    } else {
      setExpanded((oldArray) => [...oldArray, id]);
    }
  };
  const isExpandedClass = expanded.length === 0 ? "not-expanded" : "";
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
                isExpanded={expanded.includes("expired")}
                id="expired"
              >
                Expiring soon
              </AccordionToggle>
              <AccordionContent isHidden={!expanded.includes("expired")}>
                {/* <Heading title="Expiring soon" /> */}
                <NoExpiringRuns />
              </AccordionContent>
            </AccordionItem>
          </GridItem>
          <GridItem span={8} className="new-runs-container ">
            <AccordionItem>
              <AccordionToggle
                onClick={() => {
                  onToggle("newRuns");
                }}
                isExpanded={expanded.includes("newRuns")}
                id="newRuns"
              >
                New and Unmnaged
              </AccordionToggle>
              <AccordionContent isHidden={!expanded.includes("newRuns")}>
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
