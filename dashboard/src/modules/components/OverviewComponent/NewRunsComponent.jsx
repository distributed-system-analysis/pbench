import "./index.less";

import {
  DASHBOARD_SEEN,
  IS_ITEM_SEEN,
  NAME_KEY,
  ROWS_PER_PAGE,
  START_PAGE_NUMBER,
  USER_FAVORITE,
} from "assets/constants/overviewConstants";
import {
  InnerScrollContainer,
  OuterScrollContainer,
  TableComposable,
  Tbody,
  Th,
  Thead,
  Tr,
} from "@patternfly/react-table";
import { NewRunsRow, RenderPagination } from "./common-component";
import React, { useCallback, useState } from "react";
import {
  deleteDataset,
  editMetadata,
  getMetaDataActions,
  setRows,
  setRowtoEdit,
  setSelectedRuns,
} from "actions/overviewActions";
import { useDispatch, useSelector } from "react-redux";

const NewRunsComponent = () => {
  const dispatch = useDispatch();
  const { newRuns, initNewRuns, selectedRuns } = useSelector(
    (state) => state.overview
  );

  const [perPage, setPerPage] = useState(ROWS_PER_PAGE);
  const [page, setPage] = useState(START_PAGE_NUMBER);

  const onSetPage = useCallback(
    (_evt, newPage, _perPage, startIdx, endIdx) => {
      setPage(newPage);
      dispatch(setRows(newRuns.slice(startIdx, endIdx)));
    },
    [dispatch, newRuns]
  );
  const perPageOptions = [
    { title: "5", value: 5 },
    { title: "10", value: 10 },
    { title: "20", value: 20 },
  ];
  const onPerPageSelect = useCallback(
    (_evt, newPerPage, newPage, startIdx, endIdx) => {
      setPerPage(newPerPage);
      setPage(newPage);
      dispatch(setRows(newRuns.slice(startIdx, endIdx)));
    },
    [dispatch, newRuns]
  );
  const columnNames = {
    result: "Result",
    endtime: "Endtime",
  };

  /* Selecting */
  const areAllRunsSelected =
    newRuns?.length > 0 && newRuns.length === selectedRuns?.length;
  const selectAllRuns = (isSelecting) => {
    dispatch(setSelectedRuns(isSelecting ? [...newRuns] : []));
  };
  const onSelectRuns = (runs, _rowIndex, isSelecting) => {
    const otherSelectedRuns = selectedRuns.filter(
      (r) => r.resource_id !== runs.resource_id
    );
    const c = isSelecting ? [...otherSelectedRuns, runs] : otherSelectedRuns;
    dispatch(setSelectedRuns(c));
  };
  const isRowSelected = (run) =>
    selectedRuns.filter((item) => item.name === run.name).length > 0;
  /* Selecting */

  const makeFavorites = (dataset, isFavoriting = true) => {
    dispatch(getMetaDataActions(dataset, "favorite", isFavoriting));
  };
  const saveRowData = (dataset) => {
    const index = newRuns.findIndex(
      (run) => run.resource_id === dataset.resource_id
    );
    dispatch(getMetaDataActions(dataset, "datasetName", newRuns[index].name));
  };
  const moreActionItems = (dataset) => [
    {
      title: "Save",
      onClick: () => dispatch(getMetaDataActions(dataset, "save", true)),
    },
    {
      title: dataset.metadata[DASHBOARD_SEEN] ? "Mark unread" : "Mark read",
      onClick: () =>
        dispatch(
          getMetaDataActions(dataset, "read", !dataset.metadata[DASHBOARD_SEEN])
        ),
    },
    {
      title: dataset.metadata[USER_FAVORITE]
        ? "Mark unfavorite"
        : "Mark favorite",
      onClick: () =>
        dispatch(
          getMetaDataActions(
            dataset,
            "favorite",
            !dataset.metadata[USER_FAVORITE]
          )
        ),
    },
    {
      title: "Delete",
      onClick: () => dispatch(deleteDataset(dataset)),
    },
  ];

  const [expandedRunNames, setExpandedRunNames] = React.useState([]);
  const setRunExpanded = (run, isExpanding = true) =>
    setExpandedRunNames((prevExpanded) => {
      const otherExpandedRunNames = prevExpanded.filter((r) => r !== run.name);
      return isExpanding
        ? [...otherExpandedRunNames, run.name]
        : otherExpandedRunNames;
    });
  const isRunExpanded = useCallback(
    (run) => expandedRunNames.includes(run.name),
    [expandedRunNames]
  );
  const updateTblValue = (newValue, metadata, rId) => {
    dispatch(editMetadata(newValue, metadata, rId, "newRuns"));
  };
  const toggleEdit = useCallback(
    (rId, isEdit) => dispatch(setRowtoEdit(rId, isEdit, "newRuns")),
    [dispatch]
  );

  return (
    <div className="newruns-table-container">
      <OuterScrollContainer>
        <InnerScrollContainer>
          <TableComposable isStickyHeader variant={"compact"}>
            <Thead>
              <Tr>
                <Th />
                <Th
                  width={10}
                  select={{
                    onSelect: (_event, isSelecting) =>
                      selectAllRuns(isSelecting),
                    isSelected: areAllRunsSelected,
                  }}
                  style={{ borderTop: "1px solid #d2d2d2" }}
                ></Th>
                <Th width={35}>{columnNames.result}</Th>
                <Th width={25}>{columnNames.endtime}</Th>
                <Th width={20}></Th>
                <Th width={5}></Th>
                <Th width={2}></Th>
              </Tr>
            </Thead>
            <Tbody>
              {initNewRuns.map((item, rowIndex) => {
                const rowActions = moreActionItems(item);
                return (
                  <Tr
                    key={item.resource_id}
                    className={item[IS_ITEM_SEEN] ? "seen-row" : "unseen-row"}
                  >
                    <NewRunsRow
                      key={item.resource_id}
                      rowIndex={rowIndex}
                      moreActionItems={moreActionItems}
                      setRunExpanded={setRunExpanded}
                      isRunExpanded={isRunExpanded}
                      toggleEdit={toggleEdit}
                      onSelectRuns={onSelectRuns}
                      isRowSelected={isRowSelected}
                      columnNames={columnNames}
                      makeFavorites={makeFavorites}
                      saveRowData={saveRowData}
                      rowActions={rowActions}
                      item={item}
                      textInputEdit={(val) =>
                        updateTblValue(val, NAME_KEY, item.resource_id)
                      }
                    />
                  </Tr>
                );
              })}
            </Tbody>
          </TableComposable>
          <RenderPagination
            items={newRuns.length}
            page={page}
            setPage={setPage}
            perPage={perPage}
            setPerPage={setPerPage}
            onSetPage={onSetPage}
            perPageOptions={perPageOptions}
            onPerPageSelect={onPerPageSelect}
          />
        </InnerScrollContainer>
      </OuterScrollContainer>
    </div>
  );
};

export default NewRunsComponent;
