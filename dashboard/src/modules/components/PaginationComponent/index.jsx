import { Pagination, PaginationVariant } from "@patternfly/react-core";
import React from "react";

const TablePagination = ({
  numberOfRows,
  page,
  setPage,
  perPage,
  setPerPage,
}) => {
  const onSetPage = (_event, pageNumber) => {
    setPage(pageNumber);
  };
  const onPerPageSelect = (_event, perPage) => {
    setPerPage(perPage);
  };
  return (
    <Pagination
      itemCount={numberOfRows}
      widgetId="pagination-options-menu-bottom"
      variant={PaginationVariant.bottom}
      page={page}
      onSetPage={onSetPage}
      perPage={perPage}
      onPerPageSelect={onPerPageSelect}
    ></Pagination>
  );
};

export default TablePagination;
