import "./index.less";

import {
  ActionsColumn,
  InnerScrollContainer,
  OuterScrollContainer,
  TableComposable,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
} from "@patternfly/react-table";
import {
  DASHBOARD_SEEN,
  DATASET_ACCESS,
  DATASET_CREATED,
  SERVER_DELETION,
  USER_FAVORITE,
} from "assets/constants/overviewConstants";
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

import { EditRow } from "./common-component";
import { TextInput } from "@patternfly/react-core";
import { formatDateTime } from "utils/dateFunctions";

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
        dataset.metadata[DATASET_ACCESS] === "public" ? "Publish" : "Unpublish",
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
    dispatch(updateDataset(dataset, metadataType, value, "savedRuns"));
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
    createdtime: "Created Time",
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
                <Th>{columnNames.createdtime}</Th>
                <Th>{columnNames.scheduled}</Th>
                <Th>{columnNames.access}</Th>
                <Th></Th>
                <Th></Th>
              </Tr>
            </Thead>
            {savedRuns.map((item, rowIndex) => {
              const rowActions = moreActionItems(item);
              const isItemFavorited = !!item?.metadata?.[USER_FAVORITE];
              const isItemSeen = !!item?.metadata?.[DASHBOARD_SEEN];
              return (
                <Tbody key={rowIndex}>
                  <Tr
                    key={item.name}
                    className={isItemSeen ? "seen-row" : "unseen-row"}
                  >
                    <Td
                      select={{
                        rowIndex,
                        onSelect: (_event, isSelecting) =>
                          onSelectRuns(item, rowIndex, isSelecting),
                        isSelected: isRowSelected(item),
                      }}
                    />
                    <Td
                      className="result_column"
                      dataLabel={columnNames.result}
                    >
                      {item.isEdit ? (
                        <TextInput
                          validated={item.name_validated}
                          value={item.name}
                          type="text"
                          onChange={(val) =>
                            updateTblValue(val, "name", item.resource_id)
                          }
                          aria-label="saved run dataset name"
                        />
                      ) : (
                        item.name
                      )}
                    </Td>
                    <Td dataLabel={columnNames.endtime}>
                      {formatDateTime(item.metadata[DATASET_CREATED])}
                    </Td>
                    <Td dataLabel={columnNames.scheduled}>
                      {formatDateTime(item.metadata[SERVER_DELETION])}
                    </Td>
                    <Td className="access">{item.metadata[DATASET_ACCESS]}</Td>
                    <Td
                      favorites={{
                        isFavorited: isItemFavorited,
                        onFavorite: (_event, isFavoriting) =>
                          makeFavorites(item, isFavoriting),
                        rowIndex,
                      }}
                    />
                    <Td>
                      <EditRow
                        item={item}
                        toggleEdit={toggleEdit}
                        saveRowData={saveRowData}
                      />
                    </Td>
                    <Td isActionCell>
                      {rowActions ? <ActionsColumn items={rowActions} /> : null}
                    </Td>
                  </Tr>
                </Tbody>
              );
            })}
          </TableComposable>
        </InnerScrollContainer>
      </OuterScrollContainer>
    </div>
  );
};

export default SavedRunsComponent;
