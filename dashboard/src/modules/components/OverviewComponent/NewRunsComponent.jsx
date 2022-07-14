import React, { useState } from "react";
import "./index.less";
import { useDispatch, useSelector } from "react-redux";
import {
  TableComposable,
  Thead,
  Tr,
  Th,
  Tbody,
  Td,
  InnerScrollContainer,
  OuterScrollContainer,
  ActionsColumn,
  ExpandableRowContent,
} from "@patternfly/react-table";
import {
  deleteDataset,
  updateDataset,
  setRows,
  setSelectedRuns,
} from "actions/overviewActions";
import { RenderPagination } from "./common-component";
import {
  START_PAGE_NUMBER,
  ROWS_PER_PAGE,
} from "assets/constants/overviewConstants";

const NewRunsComponent = () => {
  const dispatch = useDispatch();
  const { newRuns, initNewRuns, selectedRuns } = useSelector(
    (state) => state.overview
  );
  const loginDetails = useSelector((state) => state.userAuth.loginDetails);

  const [perPage, setPerPage] = useState(ROWS_PER_PAGE);
  const [page, setPage] = useState(START_PAGE_NUMBER);

  const onSetPage = (_evt, newPage, _perPage, startIdx, endIdx) => {
    setPage(newPage);
    dispatch(setRows(newRuns.slice(startIdx, endIdx)));
  };

  const perPageOptions = [
    { title: "5", value: 5 },
    { title: "10", value: 10 },
    { title: "20", value: 20 },
  ];
  const onPerPageSelect = (_evt, newPerPage, newPage, startIdx, endIdx) => {
    setPerPage(newPerPage);
    setPage(newPage);
    dispatch(setRows(newRuns.slice(startIdx, endIdx)));
  };
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
      onClick: () => dispatch(updateDataset(dataset, "save")),
    },
    {
      title: dataset.metadata["dashboard.seen"] ? "Mark unread" : "Mark read",
      onClick: () =>
        dispatch(
          updateDataset(dataset, "read", !dataset.metadata["dashboard.seen"])
        ),
    },
    {
      title: dataset.metadata["user.favorite"]
        ? "Mark unfavorite"
        : "Mark favorite",
      onClick: () =>
        dispatch(
          updateDataset(dataset, "favorite", !dataset.metadata["user.favorite"])
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
          <TableComposable isStickyHeader>
            <Thead>
              <Tr>
                <Th width={2} />
                <Th
                  width={2}
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
              const isItemFavorited = !!item?.metadata?.["user.favorite"];
              const isItemSeen = !!item?.metadata?.["dashboard.seen"];
              return (
                <Tbody key={rowIndex}>
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
                      {item.metadata["server.deletion"]}
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
                  {item.metadata ? (
                    <Tr isExpanded={isRunExpanded(item)}>
                      <Td />
                      <Td />
                      <Td>
                        <ExpandableRowContent>
                          <div>Owner: {item.metadata["dataset.owner"]}</div>
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
