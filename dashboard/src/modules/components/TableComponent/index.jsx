import React, { useState, useEffect } from "react";
import { useDispatch } from "react-redux";
import "./index.css";
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
import SearchBox from "../SearchComponent";
import DatePickerWidget from "../DatePickerComponent";
import Heading from "../HeadingComponent";
import PathBreadCrumb from "../BreadCrumbComponent";
import AlertMessage from "../AlertComponent";
import EmptyTable from "../EmptyStateComponent";
import moment from "moment";
import { fetchPublicDatasets } from "../../../actions/fetchPublicDatasets";
import TablePagination from "../PaginationComponent";
import { constructUTCDate } from "../../../utils/constructDate";
import { formatDate } from "../../../utils/dateFormatter";
import MainLayout from "../../containers/MainLayout";
let startDate = new Date(Date.UTC(1990, 10, 4));
let endDate = constructUTCDate(new Date(formatDate(new Date())));
let controllerName = "";
let dataArray = [];
export const TableWithFavorite = () => {
  const columnNames = {
    controller: "Controller",
    name: "Name",
    creationDate: "Created On",
  };
  const [activeSortIndex, setActiveSortIndex] = useState(null);
  const [activeSortDirection, setActiveSortDirection] = useState(null);
  const [favoriteRepoNames, setFavoriteRepoNames] = useState([]);
  const [publicData, setPublicData] = useState([]);
  const [isSelected, setIsSelected] = useState("controllerListButton");
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const dispatch = useDispatch();
  useEffect(() => {
    dispatch(fetchPublicDatasets())
      .then((res) => {
        dataArray = res.data;
        setPublicData(res.data);
        setFavoriteRepoNames(
          localStorage.getItem("favControllers") !== null
            ? JSON.parse(localStorage.getItem("favControllers"))
            : []
        );
      })
      .catch((err) => {
        console.log(err);
      });
  }, []);
  const markRepoFavorited = (repo, isFavoriting = true) => {
    const otherFavorites = favoriteRepoNames.filter(
      (r) => r.name !== repo.name
    );
    const newFavorite = isFavoriting
      ? [...otherFavorites, repo]
      : otherFavorites;
    saveFavorites(newFavorite);
    setFavoriteRepoNames(newFavorite);
  };
  const selectedArray =
    isSelected === "controllerListButton"
      ? publicData.slice((page - 1) * perPage, page * perPage)
      : favoriteRepoNames.slice((page - 1) * perPage, page * perPage);

  const isRepoFavorited = (repo) =>
    !!favoriteRepoNames.find((element) => element.name === repo.name);
  const getSortableRowValues = (publicData) => {
    const { controller, name } = publicData;
    const creationDate = publicData.metadata["dataset.created"];
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
  return (
    <>
      <MainLayout>
        <AlertMessage
          message="Want to see your own data?"
          link="Login to your account"
        />
        <PageSection variant={PageSectionVariants.light}>
          <PathBreadCrumb pathList={["Dashboard", "Components"]} />
          <Heading headingTitle="Controllers"></Heading>
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
              text={`All Controllers(${publicData.length})`}
              buttonId="controllerListButton"
              isSelected={isSelected === "controllerListButton"}
              onChange={handleButtonClick}
              className="controllerListButton"
            />
            <ToggleGroupItem
              text={`Favorites(${favoriteRepoNames.length})`}
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
              {selectedArray.length > 0 ? (
                selectedArray.map((repo, rowIndex) => (
                  <Tr key={rowIndex}>
                    <Td dataLabel={columnNames.controller}>
                      <a href="#">{repo.controller}</a>
                    </Td>
                    <Td dataLabel={columnNames.name}>{repo.name}</Td>
                    <Td dataLabel={columnNames.creationDate}>
                      {moment(repo.metadata["dataset.created"]).format(
                        "YYYY-MM-DDTHH:mm"
                      )}
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
                <Td colSpan={8}>
                  <EmptyTable />
                </Td>
              )}
            </Tbody>
          </TableComposable>
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
        </PageSection>
      </MainLayout>
    </>
  );
};
