import "./index.less";

import * as CONSTANTS from "assets/constants/browsingPageConstants";

import { Checkbox, List, ListItem } from "@patternfly/react-core";
import React, { useCallback, useMemo, useState } from "react";
import { getQuisbyData, setSelectedId } from "actions/comparisonActions";
import { useDispatch, useSelector } from "react-redux";

import TablePagination from "../PaginationComponent";

const PanelConent = () => {
  const dispatch = useDispatch();

  const { publicData } = useSelector((state) => state.datasetlist);
  const {
    activeResourceId,
    isCompareSwitchChecked,
    selectedResourceIds,
    searchValue,
  } = useSelector((state) => state.comparison);
  const onFilter = useCallback(
    (item) =>
      item && (searchValue === "" || item.name.search(searchValue) >= 0),
    [searchValue]
  );
  const filteredDatasets = useMemo(
    () => publicData.filter(onFilter),
    [publicData, onFilter]
  );
  const [page, setPage] = useState(CONSTANTS.START_PAGE_NUMBER);

  return (
    <>
      {filteredDatasets.length > 0 && (
        <div className="datasets-container">
          {isCompareSwitchChecked ? (
            <div className="dataset-list-checkbox">
              {filteredDatasets.map((item) => (
                <Checkbox
                  key={item.resource_id}
                  label={item.name}
                  id={item.resource_id}
                  isChecked={selectedResourceIds?.includes(item.resource_id)}
                  onChange={(checked) =>
                    dispatch(setSelectedId(checked, item.resource_id))
                  }
                />
              ))}
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
      <TablePagination page={page} setPage={setPage} />
    </>
  );
};

export default PanelConent;
