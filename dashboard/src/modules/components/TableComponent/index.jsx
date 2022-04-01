import React, { useState, useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";
import "./index.less";
import {
  ToggleGroup,
  ToggleGroupItem,
  PageSectionVariants,
} from "@patternfly/react-core";
import {
  TableComposable,
  Thead,
  Tr,
  Th,
  Tbody,
  Td,
  OuterScrollContainer,
  InnerScrollContainer,
} from "@patternfly/react-table";
import {
  fetchPublicDatasets,
  updateFavoriteRepoNames,
  updateTblData,
  getFavoritedDatasets,
} from "actions/datasetListActions";
import TablePagination from "../PaginationComponent";
import DatePickerWidget from "../DatePickerComponent";
import PathBreadCrumb from "../BreadCrumbComponent";
import { LoginHint, Heading, EmptyTable, SearchBox } from "./common-components";
import { getTodayMidnightUTCDate, bumpToDate } from "utils/dateFunctions";

let startDate = new Date(Date.UTC(1990, 10, 4));
let endDate = bumpToDate(getTodayMidnightUTCDate(), 1);
let datasetName = "";

const TableWithFavorite = () => {
  const columnNames = {
    name: "Name",
    creationDate: "Created On",
  };
  const { endpoints } = useSelector((state) => state.apiEndpoint);
  const [activeSortIndex, setActiveSortIndex] = useState(null);
  const [activeSortDirection, setActiveSortDirection] = useState(null);
  const [isSelected, setIsSelected] = useState("datasetListButton");
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const [loginHintVisible, setLoginHintVisible] = useState(true);

  const dispatch = useDispatch();

  useEffect(() => {
    if (Object.keys(endpoints).length > 0) {
      dispatch(fetchPublicDatasets());
      dispatch(getFavoritedDatasets());
    }
  }, [dispatch, endpoints]);

  const { publicData, favoriteRepoNames, tableData } = useSelector(
    (state) => state.datasetlist
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
    isSelected === "datasetListButton"
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
  const setDatasetName = (datasetNameValue) => {
    datasetName = datasetNameValue;
  };
  const setDateRange = (startDateValue, endDateValue) => {
    startDate = startDateValue;
    endDate = endDateValue;
  };
  const saveFavorites = (fav) => {
    localStorage.setItem("favorite_datasets", JSON.stringify(fav));
  };

  const onCloseLoginHint = () => {
    setLoginHintVisible(false);
  };
  const datasetBreadcrumb = [
    { name: "Dashboard", link: "/" },
    { name: "Results", link: "" },
  ];

  return (
    <>
      {loginHintVisible && (
        <LoginHint
          message="Want to see your own data?"
          link="Login or Create an account"
          onCloseMethod={onCloseLoginHint}
          redirect="login"
        />
      )}
      <div className="table-container" variant={PageSectionVariants.light}>
        <PathBreadCrumb pathList={datasetBreadcrumb} />
        <Heading
          containerClass="publicDataPageTitle"
          headingTitle="Results"
        ></Heading>
        <div className="filterContainer">
          <SearchBox
            dataArray={tableData}
            setPublicData={setPublicData}
            startDate={startDate}
            endDate={endDate}
            setDatasetName={setDatasetName}
            aria-label="search box"
          />
          <DatePickerWidget
            dataArray={tableData}
            setPublicData={setPublicData}
            datasetName={datasetName}
            setDateRange={setDateRange}
            aria-label="date picker"
          />
        </div>
        <ToggleGroup aria-label="Result Selection Options">
          <ToggleGroupItem
            text={`All Results(${publicData?.length})`}
            buttonId="datasetListButton"
            isSelected={isSelected === "datasetListButton"}
            onChange={handleButtonClick}
            className="datasetListButton"
            aria-label="see dataset button"
          />
          <ToggleGroupItem
            text={`Favorites(${favoriteRepoNames?.length})`}
            buttonId="favoriteListButton"
            isSelected={isSelected === "favoriteListButton"}
            onChange={handleButtonClick}
            className="favoriteListButton"
            aria-label="see favorites button"
          />
        </ToggleGroup>
        <div
          style={{
            height: "200px",
          }}
        >
          <OuterScrollContainer>
            <InnerScrollContainer>
              <TableComposable
                aria-label="Favoritable table"
                variant="compact"
                isStickyHeader
              >
                <Thead>
                  <Tr>
                    <Th sort={getSortParams(1)}>{columnNames.name}</Th>
                    <Th sort={getSortParams(2)}>{columnNames.creationDate}</Th>
                    <Th sort={getSortParams(3)}></Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {selectedArray.length > 0 ? (
                    selectedArray.map((repo, rowIndex) => (
                      <Tr key={rowIndex}>
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
            </InnerScrollContainer>
          </OuterScrollContainer>
        </div>
      </div>
      <TablePagination
        numberOfControllers={
          isSelected === "controllerListButton"
            ? publicData.length
            : favoriteRepoNames.length
        }
        page={page}
        setPage={setPage}
        perPage={perPage}
        setPerPage={setPerPage}
      />
    </>
  );
};

export default TableWithFavorite;
