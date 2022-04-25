import React, { useState, useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";
import "./index.less";
import {
  ToggleGroup,
  ToggleGroupItem,
  PageSection,
  PageSectionVariants,
} from "@patternfly/react-core";
import {
  TableComposable,
  Thead,
  Tr,
  Th,
  Tbody,
  Td,
} from "@patternfly/react-table";
import {
  fetchPublicDatasets,
  updateFavoriteRepoNames,
  updateTblData,
} from "actions/publicControllerActions";
import TablePagination from "../PaginationComponent";
import DatePickerWidget from "../DatePickerComponent";
import PathBreadCrumb from "../BreadCrumbComponent";
import { LoginHint, Heading, EmptyTable, SearchBox } from "./common-components";
import { getTodayMidnightUTCDate } from "utils/getMidnightUTCDate";

let startDate = new Date(Date.UTC(1990, 10, 4));
let endDate = getTodayMidnightUTCDate();
let controllerName = "";
let dataArray = [];

const TableWithFavorite = () => {
  const columnNames = {
    controller: "Controller",
    name: "Name",
    creationDate: "Created On",
  };
  const [activeSortIndex, setActiveSortIndex] = useState(null);
  const [activeSortDirection, setActiveSortDirection] = useState(null);
  const [isSelected, setIsSelected] = useState("controllerListButton");
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const [loginHintVisible, setLoginHintVisible] = useState(true);

  const dispatch = useDispatch();

  useEffect(() => {
    dispatch(fetchPublicDatasets());
  }, [dispatch]);

  const { publicData, favoriteRepoNames } = useSelector(
    (state) => state.controller
  );
  const setPublicData = (data) => {
    dispatch(updateTblData(data));
  };
  const markRepoFavorited = (repo, isFavoriting = true) => {
    const otherFavorites = favoriteRepoNames.filter(
      (r) => r.name !== repo.name
    );
    const newFavorite = isFavoriting
      ? [...otherFavorites, repo]
      : otherFavorites;
    saveFavorites(newFavorite);
    dispatch(updateFavoriteRepoNames(newFavorite));
  };
  const selectedArray =
    isSelected === "controllerListButton"
      ? publicData?.slice((page - 1) * perPage, page * perPage)
      : favoriteRepoNames?.slice((page - 1) * perPage, page * perPage);

  const isRepoFavorited = (repo) =>
    !!favoriteRepoNames.find((element) => element.name === repo.name);

  const getSortableRowValues = (data) => {
    const { controller, name } = data;
    const creationDate = data.metadata["dataset.created"];
    return [controller, name, creationDate];
  };
  if (activeSortIndex !== null) {
    selectedArray.sort((a, b) => {
      const aValue = getSortableRowValues(a)[activeSortIndex];
      const bValue = getSortableRowValues(b)[activeSortIndex];
      if (aValue === bValue) {
        return 0;
      }
      if (activeSortDirection === "asc") {
        return aValue > bValue ? 1 : -1;
      } else {
        return bValue > aValue ? 1 : -1;
      }
    });
  }
  const getSortParams = (columnIndex) => ({
    isFavorites: columnIndex === 3,
    sortBy: {
      index: activeSortIndex,
      direction: activeSortDirection,
    },
    onSort: (_event, index, direction) => {
      setActiveSortIndex(index);
      setActiveSortDirection(direction);
    },
    columnIndex,
  });
  const handleButtonClick = (_isSelected, event) => {
    const id = event.currentTarget.id;
    setIsSelected(id);
  };
  const setControllerName = (controllerNameValue) => {
    controllerName = controllerNameValue;
  };
  const setDateRange = (startDateValue, endDateValue) => {
    startDate = startDateValue;
    endDate = endDateValue;
  };
  const saveFavorites = (fav) => {
    localStorage.setItem("favControllers", JSON.stringify(fav));
  };

  const controllerBreadcrumb = [
    { name: "Dashboard", link: "/" },
    { name: "Controllers", link: "" },
  ];

  const onCloseLoginHint = () => {
    setLoginHintVisible(false);
  };
  return (
    <>
      {loginHintVisible && (
        <LoginHint
          message="Want to see your own data?"
          link="Login or Create an account"
          onCloseMethod={onCloseLoginHint}
        />
      )}

      <PageSection variant={PageSectionVariants.light}>
        <PathBreadCrumb pathList={controllerBreadcrumb} />
        <Heading
          containerClass="publicDataPageTitle"
          headingTitle="Controllers"
        />
        <div className="filterContainer">
          <SearchBox
            dataArray={dataArray}
            setPublicData={setPublicData}
            startDate={startDate}
            endDate={endDate}
            setControllerName={setControllerName}
          />
          <DatePickerWidget
            dataArray={dataArray}
            setPublicData={setPublicData}
            controllerName={controllerName}
            setDateRange={setDateRange}
          />
        </div>
        <ToggleGroup aria-label="Result Selection Options">
          <ToggleGroupItem
            text={`All Controllers(${publicData?.length})`}
            buttonId="controllerListButton"
            isSelected={isSelected === "controllerListButton"}
            onChange={handleButtonClick}
            className="controllerListButton"
          />
          <ToggleGroupItem
            text={`Favorites(${favoriteRepoNames?.length})`}
            buttonId="favoriteListButton"
            isSelected={isSelected === "favoriteListButton"}
            onChange={handleButtonClick}
            className="favoriteListButton"
          />
        </ToggleGroup>
        <TableComposable aria-label="Favoritable table" variant="compact">
          <Thead>
            <Tr>
              <Th sort={getSortParams(0)}>{columnNames.controller}</Th>
              <Th sort={getSortParams(1)}>{columnNames.name}</Th>
              <Th sort={getSortParams(2)}>{columnNames.creationDate}</Th>
              <Th sort={getSortParams(3)}></Th>
            </Tr>
          </Thead>
          <Tbody>
            {selectedArray && selectedArray.length > 0 ? (
              selectedArray.map((repo, rowIndex) => (
                <Tr key={rowIndex}>
                  <Td dataLabel={columnNames.controller}>
                    <div className="controller-name">{repo.controller}</div>
                  </Td>
                  <Td dataLabel={columnNames.name}>{repo.name}</Td>
                  <Td dataLabel={columnNames.creationDate}>
                    {repo.metadata["dataset.created"]}
                  </Td>
                  <Td
                    favorites={{
                      isFavorited: isRepoFavorited(repo),
                      onFavorite: (_event, isFavoriting) => {
                        markRepoFavorited(repo, isFavoriting);
                      },
                      rowIndex,
                    }}
                  />
                </Tr>
              ))
            ) : (
              <Tr>
                <Td colSpan={8}>
                  <EmptyTable />
                </Td>
              </Tr>
            )}
          </Tbody>
        </TableComposable>
        <TablePagination
          numberOfControllers={
            isSelected === "controllerListButton"
              ? publicData?.length
              : favoriteRepoNames?.length
          }
          page={page}
          setPage={setPage}
          perPage={perPage}
          setPerPage={setPerPage}
        />
      </PageSection>
    </>
  );
};

export default TableWithFavorite;
