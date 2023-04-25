import * as TYPES from "actions/types";

import { Pagination, PaginationVariant } from "@patternfly/react-core";
import {
  fetchPublicDatasets,
  setPageLimit,
  setPerPage,
} from "actions/datasetListActions";
import { useDispatch, useSelector } from "react-redux";

import { OVERFETCH_FACTOR } from "assets/constants/browsingPageConstants";
import React from "react";

const TablePagination = ({ page, setPage }) => {
  const dispatch = useDispatch();

  const { totalDatasets, publicData, perPage } = useSelector(
    (state) => state.datasetlist
  );
  const onSetPage = (_event, pageNumber) => {
    setPage(pageNumber);

    fetchData(_event, pageNumber, perPage);
  };
  const onPerPageSelect = (_event, newPerPage, newPage) => {
    dispatch(setPageLimit(newPerPage * OVERFETCH_FACTOR));

    dispatch(setPerPage(newPerPage));
    setPage(newPage);

    fetchData(_event, newPage, newPerPage);
  };
  const fetchData = (_event, newPage, newPerPage = perPage) => {
    const startIdx = (newPage - 1) * newPerPage;
    const endIdx = newPage * newPerPage;
    let left = startIdx;
    let right = endIdx;
    while (left < right) {
      if (publicData[startIdx]) {
        left++;
      } else {
        break;
      }
      if (publicData[endIdx]) {
        right--;
      } else {
        break;
      }
    }
    if (left !== right) {
      dispatch({
        type: TYPES.SET_PAGE_OFFSET,
        payload: startIdx,
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
