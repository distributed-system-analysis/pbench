import "./index.less";

import {
  DASHBOARD_SEEN,
  DATASET_ACCESS,
  DEFAULT_PER_PAGE_SAVED,
  IS_ITEM_SEEN,
  NAME_KEY,
  SERVER_DELETION_KEY,
  START_PAGE_NUMBER,
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
import React, { useCallback, useState } from "react";
import { RenderPagination, SavedRunsRow } from "./common-component";
import {
  deleteDataset,
  editMetadata,
  getEditedMetadata,
  getMetaDataActions,
  publishDataset,
  setRowtoEdit,
  setSavedRows,
  setSelectedSavedRuns,
} from "actions/overviewActions";
import { useDispatch, useSelector } from "react-redux";

const SavedRunsComponent = () => {
  const dispatch = useDispatch();
  const { savedRuns, selectedSavedRuns, initSavedRuns } = useSelector(
    (state) => state.overview
  );

  /* Selecting */
  const areAllRunsSelected =
    savedRuns?.length > 0 && savedRuns?.length === selectedSavedRuns?.length;
  const selectAllRuns = (isSelecting) => {
    dispatch(setSelectedSavedRuns(isSelecting ? [...savedRuns] : []));
  };
  const onSelectRuns = (run, _rowIndex, isSelecting) => {
    const otherSelectedRuns = selectedSavedRuns.filter(
      (r) => r.resource_id !== run.resource_id
    );
    const c = isSelecting ? [...otherSelectedRuns, run] : otherSelectedRuns;
    dispatch(setSelectedSavedRuns(c));
  };
  const isRowSelected = (run) =>
    selectedSavedRuns.filter((item) => item.name === run.name).length > 0;
  /* Selecting */

  /* Actions Row */
  const moreActionItems = (dataset) => [
    {
      title:
        dataset.metadata[DATASET_ACCESS] === "public" ? "Unpublish" : "Publish",
      onClick: () => {
        const accessType =
          dataset.metadata[DATASET_ACCESS] === "public" ? "private" : "public";
        dispatch(publishDataset(dataset, accessType));
      },
    },
    {
      title: dataset.metadata[DASHBOARD_SEEN] ? "Mark unread" : "Mark read",
      onClick: () =>
        dispatch(
          getMetaDataActions(dataset, "read", !dataset.metadata[DASHBOARD_SEEN])
        ),
    },
    {
      title: "Delete",
      onClick: () => dispatch(deleteDataset(dataset)),
    },
  ];
  /* Actions Row */
  const makeFavorites = (dataset, isFavoriting = true) => {
    dispatch(getMetaDataActions(dataset, "favorite", isFavoriting));
  };
  /* Edit Dataset */
  const saveRowData = (dataset) => {
    dispatch(getEditedMetadata(dataset, "savedRuns"));
  };
  const toggleEdit = useCallback(
    (rId, isEdit) => dispatch(setRowtoEdit(rId, isEdit, "savedRuns")),
    [dispatch]
  );
  const updateTblValue = (newValue, metadata, rId) => {
    dispatch(editMetadata(newValue, metadata, rId, "savedRuns"));
  };
  /* Edit Dataset */
  /* Pagination */
  const [perPage, setPerPage] = useState(DEFAULT_PER_PAGE_SAVED);
  const [page, setPage] = useState(START_PAGE_NUMBER);

  const onSetPage = useCallback(
    (_evt, newPage, _perPage, startIdx, endIdx) => {
      setPage(newPage);
      dispatch(setSavedRows(savedRuns.slice(startIdx, endIdx)));
    },
    [dispatch, savedRuns]
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
      dispatch(setSavedRows(savedRuns.slice(startIdx, endIdx)));
    },
    [dispatch, savedRuns]
  );
  /* Pagination */
  const columnNames = {
    result: "Result",
    uploadedtime: "Uploaded Time",
    scheduled: "Scheduled for deletion on",
    access: "Access",
  };
  return (
    <div className="savedRuns-table-container">
      <OuterScrollContainer>
        <InnerScrollContainer>
          <TableComposable isStickyHeader variant={"compact"}>
            <Thead>
              <Tr>
                <Th
                  width={10}
                  select={{
                    onSelect: (_event, isSelecting) =>
                      selectAllRuns(isSelecting),
                    isSelected: areAllRunsSelected,
                  }}
                  style={{ borderTop: "1px solid #d2d2d2" }}
                ></Th>
                <Th>{columnNames.result}</Th>
                <Th>{columnNames.uploadedtime}</Th>
                <Th>{columnNames.scheduled}</Th>
                <Th>{columnNames.access}</Th>
                <Th></Th>
                <Th></Th>
                <Th></Th>
                <Th></Th>
              </Tr>
            </Thead>
            <Tbody>
              {initSavedRuns.map((item, rowIndex) => {
                const rowActions = moreActionItems(item);
                return (
                  <Tr
                    key={item.resource_id}
                    className={item[IS_ITEM_SEEN] ? "seen-row" : "unseen-row"}
                  >
                    <SavedRunsRow
                      item={item}
                      rowActions={rowActions}
                      rowIndex={rowIndex}
                      makeFavorites={makeFavorites}
                      columnNames={columnNames}
                      onSelectRuns={onSelectRuns}
                      isRowSelected={isRowSelected}
                      textInputEdit={(val) =>
                        updateTblValue(val, NAME_KEY, item.resource_id)
                      }
                      toggleEdit={toggleEdit}
                      onDateSelect={(_event, str) =>
                        updateTblValue(
                          str,
                          SERVER_DELETION_KEY,
                          item.resource_id
                        )
                      }
                      saveRowData={saveRowData}
                    />
                  </Tr>
                );
              })}
            </Tbody>
          </TableComposable>
          <RenderPagination
            items={savedRuns.length}
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

export default SavedRunsComponent;
