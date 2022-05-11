import { Pagination, PaginationVariant } from "@patternfly/react-core";
import React from "react";

function TablePagination({
  numberOfControllers,
  page,
  setPage,
  perPage,
  setPerPage,
}) {
  const onSetPage = (_event, pageNumber) => {
    setPage(pageNumber);
  };
  const onPerPageSelect = (_event, perPage) => {
    setPerPage(perPage);
  };
  return (
    <Pagination
      itemCount={numberOfControllers}
      widgetId="pagination-options-menu-bottom"
      variant={PaginationVariant.bottom}
      page={page}
      onSetPage={onSetPage}
      perPage={perPage}
      onPerPageSelect={onPerPageSelect}
    ></Pagination>
  );
}

export default TablePagination;
