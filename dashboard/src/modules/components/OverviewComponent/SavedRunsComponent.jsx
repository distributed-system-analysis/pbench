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
import { findNoOfDays, formatDateTime } from "utils/dateFunctions";
import {
  publishDataset,
  setSelectedRuns,
  updateDataset,
} from "actions/overviewActions";
import { useDispatch, useSelector } from "react-redux";

import { ProgressBar } from "./common-component";
import React from "react";

const SavedRunsComponent = () => {
  const dispatch = useDispatch();
  const { savedRuns, selectedRuns } = useSelector((state) => state.overview);
  const loginDetails = useSelector((state) => state.userAuth.loginDetails);

  /* Selecting */
  const areAllRunsSelected =
    savedRuns?.length > 0 && savedRuns?.length === selectedRuns?.length;
  const selectAllRuns = (isSelecting) => {
    dispatch(setSelectedRuns(isSelecting ? savedRuns.map((r) => r) : []));
  };
  const onSelectRuns = (run, __rowIndex, isSelecting) => {
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
        dataset.metadata["dataset.access"] === "public"
          ? "Publish"
          : "Unpublish",
      onClick: () => {
        const accessType =
          dataset.metadata["dataset.access"] === "public"
            ? "private"
            : "public";
        dispatch(publishDataset(dataset, accessType));
      },
    },
    {
      title: dataset.metadata["global.dashboard.seen"]
        ? "Mark unread"
        : "Mark read",
      onClick: () =>
        dispatch(
          updateDataset(
            dataset,
            "read",
            !dataset.metadata["global.dashboard.seen"]
          )
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
  const calculatePercent = (dateStr) => {
    const daysLeft = findNoOfDays(dateStr);
    return Math.abs(daysLeft / 1000) * 100;
  };
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
              const isItemFavorited = !!item?.metadata?.["user.favorite"];
              const isItemSeen = !!item?.metadata?.["dashboard.seen"];
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
                      {item.name}
                    </Td>
                    <Td dataLabel={columnNames.endtime}>
                      {formatDateTime(item.metadata["dataset.created"])}
                    </Td>
                    <Td dataLabel={columnNames.scheduled}>
                      {formatDateTime(item.metadata["server.deletion"])}
                      <ProgressBar
                        percent={calculatePercent(
                          item.metadata["server.deletion"]
                        )}
                        deletionTime={item.metadata["server.deletion"]}
                        title={"Title"}
                      />
                    </Td>
                    <Td className="access">
                      {item.metadata["dataset.access"]}
                    </Td>
                    <Td
                      favorites={{
                        isFavorited: isItemFavorited,
                        onFavorite: (_event, isFavoriting) =>
                          makeFavorites(item, isFavoriting),
                        rowIndex,
                      }}
                    />
                    <Td isActionCell>
                      {rowActions ? (
                        <ActionsColumn
                          items={rowActions}
                          isDisabled={
                            item?.metadata["dataset.owner"] !==
                            loginDetails?.username
                          }
                        />
                      ) : null}
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
