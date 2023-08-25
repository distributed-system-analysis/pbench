import "./index.less";

import {
  DEFAULT_PER_PAGE_EXPIRING,
  START_PAGE_NUMBER,
} from "assets/constants/overviewConstants";
import { List, ListItem } from "@patternfly/react-core";
import React, { useCallback, useState } from "react";
import { useDispatch, useSelector } from "react-redux";

import { RenderPagination } from "./common-component";
import { setExpiringRows } from "actions/overviewActions";

const ExpiringSoonComponent = () => {
  const dispatch = useDispatch();
  const { expiringRuns, initExpiringRuns } = useSelector(
    (state) => state.overview
  );

  /* Pagination */
  const [perPage, setPerPage] = useState(DEFAULT_PER_PAGE_EXPIRING);
  const [page, setPage] = useState(START_PAGE_NUMBER);

  const onSetPage = useCallback(
    (_evt, newPage, _perPage, startIdx, endIdx) => {
      setPage(newPage);
      dispatch(setExpiringRows(expiringRuns.slice(startIdx, endIdx)));
    },
    [dispatch, expiringRuns]
  );
  const perPageOptions = [
    { title: "10", value: 10 },
    { title: "15", value: 15 },
    { title: "20", value: 20 },
  ];
  const onPerPageSelect = useCallback(
    (_evt, newPerPage, newPage, startIdx, endIdx) => {
      setPerPage(newPerPage);
      setPage(newPage);
      dispatch(setExpiringRows(expiringRuns.slice(startIdx, endIdx)));
    },
    [dispatch, expiringRuns]
  );
  /* Pagination */
  return (
    <>
      <List isPlain isBordered className="expiring-soon-list">
        {initExpiringRuns.map((run) => {
          return <ListItem key={run.resource_id}>{run.name}</ListItem>;
        })}
      </List>
      <RenderPagination
        items={expiringRuns.length}
        page={page}
        setPage={setPage}
        perPage={perPage}
        setPerPage={setPerPage}
        onSetPage={onSetPage}
        perPageOptions={perPageOptions}
        onPerPageSelect={onPerPageSelect}
      />
    </>
  );
};

export default ExpiringSoonComponent;
