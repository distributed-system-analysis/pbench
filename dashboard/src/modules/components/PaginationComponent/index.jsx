import * as TYPES from "actions/types";

import { Pagination, PaginationVariant } from "@patternfly/react-core";
import {
  fetchPublicDatasets,
  setPageLimit,
  setPerPage,
} from "actions/datasetListActions";
import { useDispatch, useSelector } from "react-redux";

import React from "react";

const TablePagination = ({ page, setPage }) => {
  const dispatch = useDispatch();

  const { totalDatasets, publicData, perPage, limit } = useSelector(
    (state) => state.datasetlist
  );
  const onSetPage = (_event, pageNumber) => {
    setPage(pageNumber);

    fetchData(_event, pageNumber);
  };
  const onPerPageSelect = (_event, perPage, newPage) => {
    if (perPage > limit) {
      dispatch(setPageLimit(perPage));
    }
    dispatch(setPerPage(perPage));
    setPage(newPage);

    fetchData(_event, newPage);
  };
  const fetchData = (_event, newPage) => {
    const startIdx = (newPage - 1) * perPage;

    if (!publicData[startIdx]) {
      const offset = (newPage - 1) * perPage;

      dispatch({
        type: TYPES.SET_PAGE_OFFSET,
        payload: Number(offset),
      });
      dispatch(fetchPublicDatasets(newPage));
    }
  };

  return (
    <Pagination
      itemCount={publicData.length}
      widgetId="browsing-page-pagination"
      variant={PaginationVariant.bottom}
      page={page}
      onSetPage={onSetPage}
      perPage={perPage}
      onPerPageSelect={onPerPageSelect}
      onNextClick={fetchData}
      onLastClick={fetchData}
      toggleTemplate={({ firstIndex, lastIndex }) => (
        <React.Fragment>
          {firstIndex} - {lastIndex} of {totalDatasets}
        </React.Fragment>
      )}
    ></Pagination>
  );
};

export default TablePagination;
