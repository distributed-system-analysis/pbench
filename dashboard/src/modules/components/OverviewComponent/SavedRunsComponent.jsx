import "./index.less";

import {
  DASHBOARD_SEEN,
  DATASET_ACCESS,
  IS_ITEM_SEEN,
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
import React, { useCallback } from "react";
import {
  deleteDataset,
  editMetadata,
  publishDataset,
  setRowtoEdit,
  setSelectedRuns,
  updateDataset,
} from "actions/overviewActions";
import { useDispatch, useSelector } from "react-redux";

import { SavedRunsRow } from "./common-component";

const SavedRunsComponent = () => {
  const dispatch = useDispatch();
  const { savedRuns, selectedRuns } = useSelector((state) => state.overview);

  /* Selecting */
  const areAllRunsSelected =
    savedRuns?.length > 0 && savedRuns?.length === selectedRuns?.length;
  const selectAllRuns = (isSelecting) => {
    dispatch(setSelectedRuns(isSelecting ? [...savedRuns] : []));
  };
  const onSelectRuns = (run, _rowIndex, isSelecting) => {
    const otherSelectedRuns = selectedRuns.filter(
      (r) => r.resource_id !== run.resource_id
    );
    const c = isSelecting ? [...otherSelectedRuns, run] : otherSelectedRuns;
    dispatch(setSelectedRuns(c));
  };
  const isRowSelected = (run) =>
    selectedRuns.filter((item) => item.name === run.name).length > 0;
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
          updateDataset(dataset, "read", !dataset.metadata[DASHBOARD_SEEN])
        ),
    },
    {
      title: "Delete",
      onClick: () => dispatch(deleteDataset(dataset)),
    },
  ];
  /* Actions Row */
  const makeFavorites = (dataset, isFavoriting = true) => {
    dispatch(updateDataset(dataset, "favorite", isFavoriting));
  };
  /* Edit Dataset */
  const saveRowData = (metadataType, dataset, value) => {
    dispatch(updateDataset(dataset, metadataType, value));
  };
  const toggleEdit = useCallback(
    (rId, isEdit) => dispatch(setRowtoEdit(rId, isEdit, "savedRuns")),
    [dispatch]
  );
  const updateTblValue = (newValue, metadata, rId) => {
    dispatch(editMetadata(newValue, metadata, rId, "savedRuns"));
  };
  /* Edit Dataset */
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
                ></Th>
                <Th>{columnNames.result}</Th>
                <Th>{columnNames.uploadedtime}</Th>
                <Th>{columnNames.scheduled}</Th>
                <Th>{columnNames.access}</Th>
                <Th></Th>
                <Th></Th>
              </Tr>
            </Thead>
            <Tbody>
              {savedRuns.map((item, rowIndex) => {
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
                        updateTblValue(val, "name", item.resource_id)
                      }
                      toggleEdit={toggleEdit}
                      saveRowData={saveRowData}
                    />
                  </Tr>
                );
              })}
            </Tbody>
          </TableComposable>
        </InnerScrollContainer>
      </OuterScrollContainer>
    </div>
  );
};

export default SavedRunsComponent;
