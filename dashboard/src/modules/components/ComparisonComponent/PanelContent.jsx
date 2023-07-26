import "./index.less";

import { Checkbox, List, ListItem } from "@patternfly/react-core";
import React, { useCallback, useMemo } from "react";
import { getQuisbyData, setSelectedId } from "actions/comparisonActions";
import { useDispatch, useSelector } from "react-redux";

const PanelConent = () => {
  const dispatch = useDispatch();
  const { datasets } = useSelector((state) => state.overview);
  const {
    activeResourceId,
    isCompareSwitchChecked,
    selectedResourceIds,
    searchValue,
  } = useSelector((state) => state.comparison);
  const onFilter = useCallback(
    (item) => {
      if (searchValue === "") {
        return true;
      }
      let input;
      try {
        input = new RegExp(searchValue, "i");
      } catch (err) {
        input = new RegExp(
          searchValue.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
          "i"
        );
      }
      return item.name.search(input) >= 0;
    },
    [searchValue]
  );
  const filteredDatasets = useMemo(
    () => datasets.filter(onFilter),
    [datasets, onFilter]
  );

  return (
    <>
      {filteredDatasets.length > 0 && (
        <div className="datasets-container">
          {isCompareSwitchChecked ? (
            <div className="dataset-list-checkbox">
              {filteredDatasets.map((item) => {
                return (
                  <Checkbox
                    key={item.resource_id}
                    label={item.name}
                    id={item.resource_id}
                    isChecked={selectedResourceIds?.includes(item.resource_id)}
                    onChange={(checked) =>
                      dispatch(setSelectedId(checked, item.resource_id))
                    }
                  />
                );
              })}
            </div>
          ) : (
            <List isBordered>
              {filteredDatasets.map((item) => {
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
        </div>
      )}
    </>
  );
};

export default PanelConent;
