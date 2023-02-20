import "./index.less";

import * as APP_ROUTES from "utils/routeConstants";

import { EmptyTable, Heading, LoginHint, SearchBox } from "./common-components";
import {
  InnerScrollContainer,
  OuterScrollContainer,
  TableComposable,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
} from "@patternfly/react-table";
import React, { useEffect, useState } from "react";
import { ToggleGroup, ToggleGroupItem } from "@patternfly/react-core";
import { bumpToDate, getTodayMidnightUTCDate } from "utils/dateFunctions";
import {
  fetchPublicDatasets,
  getFavoritedDatasets,
  updateFavoriteRepoNames,
  updateTblData,
} from "actions/datasetListActions";
import { useDispatch, useSelector } from "react-redux";

import { DATASET_UPLOADED } from "assets/constants/overviewConstants";
import DatePickerWidget from "../DatePickerComponent";
import PathBreadCrumb from "../BreadCrumbComponent";
import { TOC } from "assets/constants/navigationConstants";
import TablePagination from "../PaginationComponent";
import { useNavigate } from "react-router";

let startDate = new Date(Date.UTC(1990, 10, 4));
let endDate = bumpToDate(getTodayMidnightUTCDate(), 1);
let datasetName = "";

const TableWithFavorite = () => {
  const columnNames = {
    name: "Name",
    uploadedDate: "Uploaded On",
  };
  const { endpoints } = useSelector((state) => state.apiEndpoint);
  const { loginDetails } = useSelector((state) => state.userAuth);
  const [activeSortIndex, setActiveSortIndex] = useState(null);
  const [activeSortDirection, setActiveSortDirection] = useState(null);
  const [isSelected, setIsSelected] = useState("datasetListButton");
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const [loginHintVisible, setLoginHintVisible] = useState(true);
  const navigate = useNavigate();

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
    const uploadedDate = data.metadata[DATASET_UPLOADED];
    return [data.name, uploadedDate, isRepoFavorited(data)];
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
    isFavorites: columnIndex === 2,
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
      {!loginDetails?.isLoggedIn && loginHintVisible && (
        <LoginHint
          message="Want to see your own data?"
          link="Login or Create an account"
          onCloseMethod={onCloseLoginHint}
          redirect={APP_ROUTES.AUTH}
        />
      )}
      <div className="table-container">
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
        <div className="table-scroll-container">
          <OuterScrollContainer>
            <InnerScrollContainer>
              <TableComposable
                aria-label="Favoritable table"
                variant="compact"
                isStickyHeader
              >
                <Thead>
                  <Tr>
                    <Th sort={getSortParams(0)}>{columnNames.name}</Th>
                    <Th sort={getSortParams(1)}>{columnNames.uploadedDate}</Th>
                    <Th sort={getSortParams(2)}></Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {selectedArray.length > 0 ? (
                    selectedArray.map((repo, rowIndex) => (
                      <Tr key={rowIndex}>
                        <Td
                          dataLabel={columnNames.name}
                          onClick={() => navigate(`${TOC}/${repo.resource_id}`)}
                        >
                          {repo.name}
                        </Td>
                        <Td dataLabel={columnNames.uploadedDate}>
                          {repo.metadata[DATASET_UPLOADED]}
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
        numberOfRows={
          isSelected === "datasetListButton"
            ? tableData.length
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
