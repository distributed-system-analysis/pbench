import React from "react";

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
  // Checkbox
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
import { useState } from "react";
import { useEffect } from "react";
import { useParams } from "react-router";
import axios from "axios";
import NavbarDrawer from "../NavbarDrawerComponent";
import Sidebar from "../SidebarComponent";

// let param = "";
const TableOfContent = () => {
  const [menuDrilledIn, setMenuDrilledIn] = useState([]);
  const [drilldownPath, setDrillDownPath] = useState([]);
  const [menuHeights, setMenuHeights] = useState({});
  const [activeMenu, setActiveMenu] = useState("rootMenu");
  const [breadCrumb, setBreadCrumb] = useState(undefined);
  const [activeFile, setActiveFile] = useState(-1);
  const [currData, setCurrData] = useState([]);
  const [tableData, setTableData] = useState([]);
  const [breadCrumbLabels, setBreadCrumbLabels] = useState([]);
  const [stack, setStack] = useState([]);
  const [pathList, setPathList] = useState(new Set());
  const [param,setParam]=useState("")
  let count = 0;
  let count2 = 0;
  // const [withMaxMenuHeight,setWithMaxMenuHeight]=useState(false)
  const [contentData, setContentData] = useState([]);
  const params = useParams();
  console.log("start");
  useEffect(() => {
    axios
      .post(`http://10.1.170.201/api/v1/datasets/contents/${params["*"]}`, {
        parent: "/",
      })
      .then((res) => {
        setStack([...stack, res.data]);
        setTableData(res.data);
        setContentData(res.data);
      })
      .catch((err) => console.log(err));
  }, []);
 console.log("here",breadCrumbLabels)
  const onToggle = (isOpen, key,moreBreadCrumbs) => {
    console.log(moreBreadCrumbs)
    switch (key) {
      case "app":
        setBreadCrumb(appGroupingBreadcrumb(isOpen, moreBreadCrumbs));
        break;
      default:
        break;
    }
  };

  // const onToggleMaxMenuHeight = checked => {
  //   setWithMaxMenuHeight(checked);
  // };

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
  const getDropDown = (moreBreadCrumbs) => {
    console.log("OOOOOOOOOO");
    console.log(breadCrumbLabels);
    console.log(moreBreadCrumbs);
    const dropDownArray = moreBreadCrumbs
      .map((label, index) => {
        // if (index >= 0 && index < breadCrumbLabels.length)
        if(index>=0&&index!=moreBreadCrumbs.length-1){
          return (
            <DropdownItem
              key="dropdown-start"
              component="button"
              icon={<AngleLeftIcon />}
              onClick={() => {
                stack.length = index + 2;
                setStack(stack);
                const x = breadCrumbLabels.slice(0, index + 1);
                // breadCrumbLabels=x;
                // console.log(x)
                // setCurrPath(stack.slice(0,index).join("/"));
                // console.log(stack.slice(0,index).join("/"));
                // console.log(path)
                // console.log(currPath)
                console.log(x);
                const newParam=param.split("/");
                //  console.log(newParam.slice(0,index+1).join("/"))
                setParam(newParam.slice(0,index+1).join("/"))
                setBreadCrumbLabels(x);
                setCurrData(stack[index + 1]);
                setTableData(stack[index + 1]);
                setBreadCrumb(appGroupingBreadcrumb(false, x));
              }}
            >
              {label}
            </DropdownItem>
          );}
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
          setStack(stack);
          console.log(stack);
          setTableData(stack[0]);
          // setTableData(stack[stack.length-1])
        }}
      >
        Rooti
      </BreadcrumbItem>
      <BreadcrumbHeading component="button">{initial[0]}</BreadcrumbHeading>
    </Breadcrumb>
  );

  const appGroupingBreadcrumb = (isOpen, moreBreadCrumbs) => {
    {
      console.log(moreBreadCrumbs);
    }
    return (
      <Breadcrumb>
        <BreadcrumbItem
          component="button"
          onClick={() => {
            drillOut("rootMenu", "group:start_rollout", null);
            stack.length = 1;
            setStack(stack);
            console.log(stack);
            setTableData(stack[0]);
          }}
        >
          Root
        </BreadcrumbItem>
        <BreadcrumbItem isDropdown>
          <Dropdown
            toggle={
              <BadgeToggle
                id="toggle-id"
                onToggle={(open) => onToggle(open, "app",moreBreadCrumbs)}
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

  // const labelsBreadcrumb = (isOpen) => (
  //   <Breadcrumb>
  //     <BreadcrumbItem
  //       component="button"
  //       onClick={() => drillOut("rootMenu", "group:start_rollout", null)}
  //     >
  //       Root
  //     </BreadcrumbItem>
  //     <BreadcrumbItem isDropdown>
  //       <Dropdown
  //         toggle={
  //           <BadgeToggle
  //             id="toggle-id"
  //             onToggle={(open) => onToggle(open, "label")}
  //           >
  //             1
  //           </BadgeToggle>
  //         }
  //         isOpen={isOpen}
  //         dropdownItems={[
  //           <DropdownItem
  //             key="dropdown-start"
  //             component="button"
  //             icon={<AngleLeftIcon />}
  //             onClick={() =>
  //               drillOut(
  //                 "drilldownMenuStart",
  //                 "group:labels_start",
  //                 startRolloutBreadcrumb
  //               )
  //             }
  //           >
  //             Start rollout
  //           </DropdownItem>,
  //         ]}
  //       />
  //     </BreadcrumbItem>
  //     <BreadcrumbHeading component="button">Labels</BreadcrumbHeading>
  //   </Breadcrumb>
  // );

  const getSubFolderData = (data) => {
    console.log(data);
    axios
      .post(`http://10.1.170.201/api/v1/datasets/contents/${params["*"]}`, {
        parent: `/${data}`,
      })
      .then((res) => {
        setTableData(res.data);
        setStack([...stack, res.data]);
        setCurrData(res.data);
        setPathList(pathList.add(data));
      })
      .catch((err) => {
        console.log(err);
      });
  };
  return (
    <>
      {/* <Checkbox
          label="Set max menu height"
          isChecked={withMaxMenuHeight}
          onChange={onToggleMaxMenuHeight}
          aria-label="Set max menu height checkbox"
          id="toggle-max-menu-height"
          name="toggle-max-menu-height"
        /> */}
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
            <MenuContent>
              {/* menuHeight={`${menuHeights[activeMenu]}px`} maxMenuHeight={withMaxMenuHeight ? '100px' : 'auto'} */}

              <MenuList>
                {contentData?.directories?.map((data, index) => {
                  return (
                    <MenuItem
                      itemId="group:start_rollout"
                      id="d_down_parent"
                      key={index}
                      direction="down"
                      onClick={() => {
                        console.log("hhhh")
                        breadCrumbLabels.push(data);
                        setBreadCrumbLabels(breadCrumbLabels);
                        setBreadCrumb(initialBreadcrumb(breadCrumbLabels));
                        if (param.length === 0) {
                          const x = param.concat(data);
                          setParam(x);
                          getSubFolderData(x);
                        } else {
                          const x = param.concat("/", data);
                          param = x;
                        }
                        console.log(param);
                        // getSubFolderData(x);
                      }}
                      drilldownMenu={
                        <DrilldownMenu id="drilldownMenuStart">
                          {currData?.directories?.map((data, index) => {
                            if (count < currData.directories.length) {
                              count = count + 1;
                              return (
                                <MenuItem
                                  itemId="dir_info"
                                  id="d_down"
                                  key={index}
                                  direction="down"
                                  onClick={() => {
                                    breadCrumbLabels.push(data);
                                    console.log("iiiiii")
                                    setBreadCrumbLabels(breadCrumbLabels);
                                    setBreadCrumb(
                                      appGroupingBreadcrumb(
                                        false,
                                        breadCrumbLabels
                                      )
                                    );
                                    const x = param.concat("/", data);
                                    setParam(x);
                                    console.log(param);
                                    getSubFolderData(x);
                                  }}
                                >
                                  <FolderIcon />
                                  {data}
                                </MenuItem>
                              );
                            }
                          })}

                          {currData?.files?.map((data, index) => {
                            if (count2 < currData.files.length) {
                              count2 = count2 + 1;
                              return (
                                <MenuItem
                                  key={index}
                                  onClick={() => setActiveFile(index)}
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
                    <MenuItem key={index} onClick={() => setActiveFile(index)}>
                      {data.name}
                    </MenuItem>
                  );
                })}
              </MenuList>
            </MenuContent>
          </Menu>
          <TableComposable aria-label="Simple table" variant="compact">
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
              {tableData?.files?.map((file, index) => (
                <Tr
                  key={file.name}
                  className={activeFile === index ? "active" : ""}
                >
                  <Td dataLabel={file.name}>{file.name}</Td>
                  <Td dataLabel={file.mtime}>{file.mtime}</Td>
                  <Td dataLabel={file.size}>{file.size}</Td>
                  <Td dataLabel={file.mode}>{file.mode}</Td>
                  <Td dataLabel={file.type}>{file.type}</Td>
                </Tr>
              ))}
            </Tbody>
          </TableComposable>
        </div>
      </Page>
    </>
  );
};

export default TableOfContent;
