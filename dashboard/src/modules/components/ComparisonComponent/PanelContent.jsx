import "./index.less";

import { List, ListItem } from "@patternfly/react-core";
import { useDispatch, useSelector } from "react-redux";

import React from "react";
import { getQuisbyData } from "actions/comparisonActions";

const PanelConent = () => {
  const dispatch = useDispatch();
  const { datasets } = useSelector((state) => state.overview);
  const { activeResourceId } = useSelector((state) => state.comparison);

  return (
    <>
      {datasets.length > 0 && (
        <List isBordered>
          {datasets.map((item) => {
            const isActiveItem = item.resource_id === activeResourceId;
            const itemClassName = isActiveItem
              ? "dataset-item active-item"
              : "dataset-item";
            return (
              <ListItem
                className={itemClassName}
                onClick={() => dispatch(getQuisbyData(item))}
                key={item.resource_id}
              >
                {item.name}
              </ListItem>
            );
          })}
        </List>
      )}
    </>
  );
};

export default PanelConent;
