import "./index.less";

import {
  ActionsColumn,
  ExpandableRowContent,
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
  DATASET_OWNER,
  ROWS_PER_PAGE,
  SERVER_DELETION,
  START_PAGE_NUMBER,
  USER_FAVORITE,
} from "assets/constants/overviewConstants";
import React, { useCallback, useState } from "react";
import {
  deleteDataset,
  setRows,
  setSelectedRuns,
  updateDataset,
} from "actions/overviewActions";
import { useDispatch, useSelector } from "react-redux";

import { RenderPagination } from "./common-component";
import { formatDateTime } from "utils/dateFunctions";

const NewRunsComponent = () => {
  const dispatch = useDispatch();
  const { newRuns, initNewRuns, selectedRuns } = useSelector(
    (state) => state.overview
  );
  // const loginDetails = useSelector((state) => state.userAuth.loginDetails);

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
    dispatch(updateDataset(dataset, "favorite", isFavoriting));
  };

  const moreActionItems = (dataset) => [
    {
      title: "Save",
      onClick: () => dispatch(updateDataset(dataset, "save", true)),
    },
    {
      title: dataset.metadata[DASHBOARD_SEEN] ? "Mark unread" : "Mark read",
      onClick: () =>
        dispatch(
          updateDataset(dataset, "read", !dataset.metadata[DASHBOARD_SEEN])
        ),
    },
    {
      title: dataset.metadata[USER_FAVORITE]
        ? "Mark unfavorite"
        : "Mark favorite",
      onClick: () =>
        dispatch(
          updateDataset(dataset, "favorite", !dataset.metadata[USER_FAVORITE])
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
  const isRunExpanded = (run) => expandedRunNames.includes(run.name);

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
                ></Th>
                <Th width={35}>{columnNames.result}</Th>
                <Th width={25}>{columnNames.endtime}</Th>
                <Th width={20}></Th>
                <Th width={2}></Th>
              </Tr>
            </Thead>

            {initNewRuns.map((item, rowIndex) => {
              const rowActions = moreActionItems(item);
              const isItemFavorited = !!item?.metadata?.[USER_FAVORITE];
              const isItemSeen = !!item?.metadata?.[DASHBOARD_SEEN];
              return (
                <Tbody key={rowIndex} isExpanded={isRunExpanded(item)}>
                  <Tr
                    key={item.name}
                    className={isItemSeen ? "seen-row" : "unseen-row"}
                  >
                    <Td
                      expand={
                        item.metadata
                          ? {
                              rowIndex,
                              isExpanded: isRunExpanded(item),
                              onToggle: () =>
                                setRunExpanded(item, !isRunExpanded(item)),
                              expandId: "composable-expandable-example",
                            }
                          : undefined
                      }
                    />
                    <Td
                      select={{
                        rowIndex,
                        onSelect: (_event, isSelecting) =>
                          onSelectRuns(item, rowIndex, isSelecting),
                        isSelected: isRowSelected(item),
                      }}
                    />
                    <Td dataLabel={columnNames.result}>{item.name}</Td>
                    <Td dataLabel={columnNames.endtime}>
                      {formatDateTime(item.metadata[SERVER_DELETION])}
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
                          // isDisabled={
                          //   item?.metadata[DATASET_OWNER] !==
                          //   loginDetails?.username
                          // }
                        />
                      ) : null}
                    </Td>
                  </Tr>
                  {item.metadata ? (
                    <Tr isExpanded={isRunExpanded(item)}>
                      <Td />
                      <Td />
                      <Td>
                        <ExpandableRowContent>
                          <div>Owner: {item.metadata[DATASET_OWNER]}</div>
                        </ExpandableRowContent>
                      </Td>
                    </Tr>
                  ) : null}
                </Tbody>
              );
            })}
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
