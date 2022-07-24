import React, { useState, useEffect } from "react";
import { useParams } from "react-router";
import "./index.less";
import {
  Menu,
  MenuContent,
  MenuList,
  MenuItem,
  Divider,
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbHeading,
  DrilldownMenu,
  MenuBreadcrumb,
  Dropdown,
  DropdownItem,
  BadgeToggle,
  Page,
  Spinner,
} from "@patternfly/react-core";
import {
  TableComposable,
  Thead,
  Tr,
  Th,
  Tbody,
  Td,
} from "@patternfly/react-table";
import AngleLeftIcon from "@patternfly/react-icons/dist/esm/icons/angle-left-icon";
import FolderIcon from "@patternfly/react-icons/dist/esm/icons/folder-icon";
import NavbarDrawer from "../NavbarDrawerComponent";
import Sidebar from "../SidebarComponent";
import TablePagination from "../PaginationComponent";
import { SearchTOC } from "./common-components";
import { EmptyTable } from "../TableComponent/common-components";
import { fetchTOC } from "actions/tableOfContentActions";
import { useDispatch, useSelector } from "react-redux";
import { updateTableData } from "actions/tableOfContentActions";
import { updateSearchSpace } from "actions/tableOfContentActions";
import { updateStack } from "actions/tableOfContentActions";
import { updateCurrData } from "actions/tableOfContentActions";
import { updateTOCLoader } from "actions/tableOfContentActions";

let datasetName = "";
console.log(datasetName);
const TableOfContent = () => {
  const [menuDrilledIn, setMenuDrilledIn] = useState([]);
  const [drilldownPath, setDrillDownPath] = useState([]);
  const [menuHeights, setMenuHeights] = useState({});
  const [activeMenu, setActiveMenu] = useState("rootMenu");
  const [breadCrumb, setBreadCrumb] = useState(undefined);
  const [activeFile, setActiveFile] = useState(-1);
  const [breadCrumbLabels, setBreadCrumbLabels] = useState([]);
  const [param, setParam] = useState("");
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(5);
  const params = useParams();
  const dispatch = useDispatch();
  let dirCount = 0;
  let fileCount = 0;
  useEffect(() => {
    dispatch(fetchTOC(params["*"], "/", false));
  }, []);
  const { stack, searchSpace, tableData, contentData, currData, isLoading } =
    useSelector((state) => state.tableOfContent);
  const setTableData = (data) => {
    dispatch(updateTableData(data));
  };
  const setSearchSpace = (data) => {
    dispatch(updateSearchSpace(data));
  };
  const setStack = (data) => {
    dispatch(updateStack(data));
  };
  const setCurrData = (data) => {
    dispatch(updateCurrData(data));
  };
  const setIsLoading = (data) => {
    dispatch(updateTOCLoader(data));
  };
  const onToggle = (isOpen, key, moreBreadCrumbs) => {
    switch (key) {
      case "app":
        setBreadCrumb(appGroupingBreadcrumb(isOpen, moreBreadCrumbs));
        break;
      default:
        break;
    }
  };

  const visibleTableFiles = tableData
    ? tableData.slice((page - 1) * perPage, page * perPage)
    : [];
  const drillOut = (toMenuId, fromPathId, breadcrumb) => {
    const indexOfMenuId = menuDrilledIn.indexOf(toMenuId);
    const menuDrilledInSansLast = menuDrilledIn.slice(0, indexOfMenuId);
    const indexOfMenuIdPath = drilldownPath.indexOf(fromPathId);
    const pathSansLast = drilldownPath.slice(0, indexOfMenuIdPath);
    setMenuDrilledIn(menuDrilledInSansLast);
    setDrillDownPath(pathSansLast);
    setActiveMenu(toMenuId);
    setBreadCrumb(breadCrumb);
  };
  const setHeight = (menuId, height) => {
    if (!menuHeights[menuId]) {
      setMenuHeights({ ...menuHeights, [menuId]: height });
    }
  };
  const drillIn = (fromMenuId, toMenuId, pathId) => {
    setMenuDrilledIn([...menuDrilledIn, fromMenuId]);
    setDrillDownPath([...drilldownPath, pathId]);
    setActiveMenu(toMenuId);
  };
  const setDatasetName = (datasetNameValue) => {
    datasetName = datasetNameValue;
  };
  const getDropDown = (moreBreadCrumbs) => {
    const dropDownArray = moreBreadCrumbs.map((label, index) => {
      if (index >= 0 && index != moreBreadCrumbs.length - 1) {
        return (
          <DropdownItem
            key="dropdown-start"
            component="button"
            icon={<AngleLeftIcon />}
            onClick={() => {
              stack.length = index + 2;
              setStack(stack);
              const updatedBreadCrumbLabels = breadCrumbLabels.slice(
                0,
                index + 1
              );
              const newParam = param.split("/");
              setParam(newParam.slice(0, index + 1).join("/"));
              setBreadCrumbLabels(updatedBreadCrumbLabels);
              setCurrData(stack[index + 1]);
              setTableData(stack[index + 1].files);
              setSearchSpace(stack[index + 1].files);
              if (updatedBreadCrumbLabels.length === 1) {
                setBreadCrumb(initialBreadcrumb(updatedBreadCrumbLabels));
              } else if (updatedBreadCrumbLabels.length > 1)
                setBreadCrumb(
                  appGroupingBreadcrumb(false, updatedBreadCrumbLabels)
                );
            }}
          >
            {label}
          </DropdownItem>
        );
      }
    });
    dropDownArray.pop();
    return dropDownArray;
  };
  const initialBreadcrumb = (initial) => (
    <Breadcrumb>
      <BreadcrumbItem
        component="button"
        onClick={() => {
          drillOut("rootMenu", "group:start_rollout", null);
          stack.length = 1;
          initial = [];
          setStack(stack);
          setParam("");
          setTableData(stack[0].files);
          setBreadCrumbLabels([]);
          setBreadCrumb(initialBreadcrumb(initial));
          setSearchSpace(stack[0].files);
        }}
      >
        Root
      </BreadcrumbItem>
      <BreadcrumbHeading component="button">
        {initial.length > 0 ? initial[0] : ""}
      </BreadcrumbHeading>
    </Breadcrumb>
  );

  const appGroupingBreadcrumb = (isOpen, moreBreadCrumbs) => {
    return (
      <Breadcrumb>
        <BreadcrumbItem
          component="button"
          onClick={() => {
            drillOut("rootMenu", "group:start_rollout", null);
            stack.length = 1;
            moreBreadCrumbs = [];
            setStack(stack);
            setTableData(stack[0].files);
            setSearchSpace(stack[0].files);
            setBreadCrumb(initialBreadcrumb([]));
            setParam("");
            setBreadCrumbLabels([]);
          }}
        >
          Root
        </BreadcrumbItem>
        <BreadcrumbItem isDropdown>
          <Dropdown
            toggle={
              <BadgeToggle
                id="toggle-id"
                onToggle={(open) => onToggle(open, "app", moreBreadCrumbs)}
              >
                {moreBreadCrumbs.length - 1}
              </BadgeToggle>
            }
            isOpen={isOpen}
            dropdownItems={getDropDown(moreBreadCrumbs)}
          />
        </BreadcrumbItem>
        <BreadcrumbHeading component="button">
          {moreBreadCrumbs[moreBreadCrumbs.length - 1]}
        </BreadcrumbHeading>
      </Breadcrumb>
    );
  };
  const getSubFolderData = (data) => {
    dispatch(fetchTOC(params["*"], `/${data}`, true));
  };
  return (
    <>
      <Page header={<NavbarDrawer />} sidebar={<Sidebar />}>
        <div className="toc">
          <br />

          <Menu
            id="rootMenu"
            containsDrilldown
            drilldownItemPath={drilldownPath}
            drilledInMenus={menuDrilledIn}
            activeMenu={activeMenu}
            onDrillIn={drillIn}
            onDrillOut={drillOut}
            onGetMenuHeight={setHeight}
          >
            {breadCrumb && (
              <>
                <MenuBreadcrumb>{breadCrumb}</MenuBreadcrumb>
                <Divider component="li" />
              </>
            )}
            {isLoading ? (
              <Spinner className="spinner"></Spinner>
            ) : (
              <MenuContent>
                <MenuList>
                  {contentData?.directories?.map((data, index) => {
                    return (
                      <MenuItem
                        itemId="group:start_rollout"
                        id="d_down_parent"
                        key={index}
                        direction="down"
                        onClick={() => {
                          breadCrumbLabels.push(data);
                          setBreadCrumbLabels(breadCrumbLabels);
                          setBreadCrumb(initialBreadcrumb(breadCrumbLabels));
                          const dirPath = param.concat(data);
                          setParam(dirPath);
                          setIsLoading(true);
                          getSubFolderData(dirPath);
                        }}
                        drilldownMenu={
                          <DrilldownMenu id="drilldownMenuStart">
                            {currData?.directories?.map((data, index) => {
                              if (dirCount < currData.directories.length) {
                                dirCount = dirCount + 1;
                                return (
                                  <MenuItem
                                    itemId="dir_info"
                                    id="d_down"
                                    key={index}
                                    direction="down"
                                    onClick={() => {
                                      breadCrumbLabels.push(data);
                                      setBreadCrumbLabels(breadCrumbLabels);
                                      setBreadCrumb(
                                        appGroupingBreadcrumb(
                                          false,
                                          breadCrumbLabels
                                        )
                                      );
                                      const dirPath = param.concat("/", data);
                                      setParam(dirPath);
                                      setIsLoading(true);
                                      getSubFolderData(dirPath);
                                    }}
                                  >
                                    <FolderIcon />
                                    {data}
                                  </MenuItem>
                                );
                              }
                            })}

                            {currData?.files?.map((data, index) => {
                              if (fileCount < currData.files.length) {
                                fileCount = fileCount + 1;
                                return (
                                  <MenuItem
                                    key={index}
                                    onClick={() => {
                                      if (index >= page * perPage) {
                                        setPage(page + 1);
                                        setActiveFile(index);
                                      } else if (index < (page - 1) * perPage) {
                                        setPage(page - 1);
                                        setActiveFile(index);
                                      } else {
                                        setActiveFile(index);
                                      }
                                    }}
                                  >
                                    {data.name}
                                  </MenuItem>
                                );
                              }
                            })}
                          </DrilldownMenu>
                        }
                      >
                        <FolderIcon />
                        {data}
                      </MenuItem>
                    );
                  })}
                  {contentData?.files?.map((data, index) => {
                    return (
                      <MenuItem
                        key={index}
                        onClick={() => {
                          if (index >= page * perPage) {
                            setPage(page + 1);
                            setActiveFile(index);
                          } else if (index < (page - 1) * perPage) {
                            setPage(page - 1);
                            setActiveFile(index);
                          } else {
                            setActiveFile(index);
                          }
                        }}
                      >
                        {data.name}
                      </MenuItem>
                    );
                  })}
                </MenuList>
              </MenuContent>
            )}
          </Menu>
          <div className="tableTOC">
            <div className="searchTOCContainer">
              <SearchTOC
                dataArray={searchSpace}
                setTableData={setTableData}
                setDatasetName={setDatasetName}
              ></SearchTOC>
            </div>
            <TableComposable
              aria-label="Simple table"
              variant="compact"
              className="tocBody"
            >
              {isLoading ? (
                <Spinner className="spinner"></Spinner>
              ) : (
                <>
                  <Thead>
                    <Tr>
                      <Th>name</Th>
                      <Th>mtime</Th>
                      <Th>size</Th>
                      <Th>mode</Th>
                      <Th>type</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {visibleTableFiles.length > 0 ? (
                      visibleTableFiles?.map((file, index) => (
                        <Tr
                          key={file.name}
                          className={
                            activeFile === index + (page - 1) * perPage
                              ? "active"
                              : ""
                          }
                        >
                          <Td dataLabel={file.name}>{file.name}</Td>
                          <Td dataLabel={file.mtime}>{file.mtime}</Td>
                          <Td dataLabel={file.size}>{file.size}</Td>
                          <Td dataLabel={file.mode}>{file.mode}</Td>
                          <Td dataLabel={file.type}>{file.type}</Td>
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
                </>
              )}
            </TableComposable>
            <TablePagination
              numberOfRows={tableData.length}
              page={page}
              setPage={setPage}
              perPage={perPage}
              setPerPage={setPerPage}
            />
          </div>
        </div>
      </Page>
    </>
  );
};

export default TableOfContent;
