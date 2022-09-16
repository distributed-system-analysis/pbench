import "./index.less";

import { List, ListItem } from "@patternfly/react-core";

import React from "react";
import { useSelector } from "react-redux";

const ExpiringSoonComponent = () => {
  const { expiringRuns } = useSelector((state) => state.overview);

  return (
    <List isPlain isBordered>
      {expiringRuns.map((run) => {
        return <ListItem key={run.resource_id}>{run.name}</ListItem>;
      })}
    </List>
  );
};

export default ExpiringSoonComponent;
