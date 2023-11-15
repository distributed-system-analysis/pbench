import "./index.less";

import * as APP_ROUTES from "utils/routeConstants";
import * as CONSTANTS from "assets/constants/browsingPageConstants";

import { EmptyTable, Heading, LoginHint, SearchBox } from "./common-components";
import { HOME, TOC } from "utils/routeConstants";
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
import {
  fetchPublicDatasets,
  getFavoritedDatasets,
  updateFavoriteRepoNames,
} from "actions/datasetListActions";
import { useDispatch, useSelector } from "react-redux";

import Cookies from "js-cookie";
import DatePickerWidget from "../DatePickerComponent";
import { RESULTS } from "assets/constants/compareConstants";
import { RenderPagination } from "../OverviewComponent/common-component";
import TablePagination from "../PaginationComponent";
import { ViewOptions } from "../ComparisonComponent/common-components";
import { useKeycloak } from "@react-keycloak/web";
import { useNavigate } from "react-router";

const TableWithFavorite = () => {
  const columnNames = {
    name: "Name",
    uploadedDate: "Uploaded On",
  };
  const loggedIn = Cookies.get("isLoggedIn");
  const { endpoints } = useSelector((state) => state.apiEndpoint);
  const { keycloak } = useKeycloak();
  const [activeSortIndex, setActiveSortIndex] = useState(null);
  const [activeSortDirection, setActiveSortDirection] = useState(null);
  const [isSelected, setIsSelected] = useState("datasetListButton");

  const [loginHintVisible, setLoginHintVisible] = useState(true);

  const [favTblperPage, setfavTblPerPage] = useState(
    CONSTANTS.DEFAULT_PER_PAGE
  );
  const [favPage, setFavPage] = useState(CONSTANTS.START_PAGE_NUMBER);
  const [page, setPage] = useState(CONSTANTS.START_PAGE_NUMBER);

  const navigate = useNavigate();
  const dispatch = useDispatch();

  useEffect(() => {
    if (Object.keys(endpoints).length > 0) {
      dispatch(fetchPublicDatasets(CONSTANTS.START_PAGE_NUMBER));
      dispatch(getFavoritedDatasets());
    }
  }, [dispatch, endpoints]);

  const { publicData, favoriteRepoNames, perPage } = useSelector(
    (state) => state.datasetlist
  );

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

  let selectedArray =
    isSelected === "datasetListButton"
      ? publicData?.slice((page - 1) * perPage, page * perPage)
      : favoriteRepoNames?.slice(
          (favPage - 1) * favTblperPage,
          favPage * favTblperPage
        );

  const isRepoFavorited = (repo) =>
    !!favoriteRepoNames?.find((element) => element?.name === repo?.name);

  const getSortableRowValues = (data) => {
    const uploadedDate = data.metadata.dataset.uploaded;
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

  const saveFavorites = (fav) => {
    localStorage.setItem("favorite_datasets", JSON.stringify(fav));
  };

  const onCloseLoginHint = () => {
    setLoginHintVisible(false);
  };

  /* Favorite Table Pagination */
  const onSetPage = (_evt, newPage, _perPage, startIdx, endIdx) => {
    setFavPage(newPage);
    selectedArray = favoriteRepoNames?.slice(startIdx, endIdx);
  };

  const onPerPageSelect = (_evt, newPerPage, newPage, startIdx, endIdx) => {
    setfavTblPerPage(newPerPage);
    setFavPage(newPage);
    selectedArray = favoriteRepoNames?.slice(startIdx, endIdx);
  };
  /* Favorite Table Pagination*/
  return (
    <>
      {!keycloak.authenticated && loginHintVisible && (
        <LoginHint
          message="Want to see your own data?"
          link="Login or Create an account"
          onCloseMethod={onCloseLoginHint}
          redirect={APP_ROUTES.AUTH}
        />
      )}
      <div className="table-container">
        <Heading
          containerClass="publicDataPageTitle"
          headingTitle="Results"
        ></Heading>
        <div className="filterContainer">
          <SearchBox setPage={setPage} aria-label="search box" />
          <DatePickerWidget setPage={setPage} aria-label="date picker" />
          {loggedIn && (
            <>
              {" "}
              <span className="runs-text">Datasets</span>
              <ViewOptions currPage={RESULTS} />
            </>
          )}
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
                      <Tr key={repo?.resource_id}>
                        <Td
                          className="dataset_name"
                          dataLabel={columnNames.name}
                          onClick={() =>
                            navigate(`/${HOME}${TOC}/${repo?.resource_id}`)
                          }
                        >
                          {repo?.name}
                        </Td>
                        <Td dataLabel={columnNames.uploadedDate}>
                          {repo?.metadata.dataset.uploaded}
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
                    <Tr key={"empty-row"}>
                      <Td colSpan={8}>
                        <EmptyTable />
                      </Td>
                    </Tr>
                  )}
                </Tbody>
              </TableComposable>
              {isSelected === "datasetListButton" ? (
                <TablePagination page={page} setPage={setPage} />
              ) : (
                <RenderPagination
                  items={favoriteRepoNames.length}
                  page={favPage}
                  setPage={setFavPage}
                  perPage={favTblperPage}
                  setPerPage={setfavTblPerPage}
                  onSetPage={onSetPage}
                  perPageOptions={CONSTANTS.PER_PAGE_OPTIONS}
                  onPerPageSelect={onPerPageSelect}
                />
              )}
            </InnerScrollContainer>
          </OuterScrollContainer>
        </div>
      </div>
    </>
  );
};

export default TableWithFavorite;
