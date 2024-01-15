import "./index.less";

import {
  Divider,
  Flex,
  FlexItem,
  List,
  ListItem,
  Sidebar,
  SidebarContent,
  SidebarPanel,
} from "@patternfly/react-core";
import React, { useEffect } from "react";
import { fetchTOC, setActiveFileContent } from "actions/tocActions";
import { useDispatch, useSelector } from "react-redux";

import { DownloadIcon } from "@patternfly/react-icons";
import DrilldownMenu from "./DrillDownMenu";
import { useParams } from "react-router";

const TableOfContent = () => {
  const dispatch = useDispatch();
  const params = useParams();

  const { endpoints } = useSelector((state) => state.apiEndpoint);
  const { activeFile, inventoryDownloadLink } = useSelector(
    (state) => state.toc
  );
  useEffect(() => {
    if (Object.keys(endpoints).length > 0)
      dispatch(fetchTOC(params["dataset_id"], "", undefined, false));
  }, [dispatch, endpoints, params]);

  const drillMenuItem = (item) => {
    if (!item.isDirectory) {
      dispatch(setActiveFileContent(item));
    } else if (!item.children.length) {
      dispatch(
        fetchTOC(
          params["dataset_id"],
          item.id.replaceAll("*", "/"),
          item.id,
          true
        )
      );
    }
  };
  return (
    <div className="toc-container">
      <Flex className="heading-container">
        <FlexItem className="heading">
          Dataset Name:
          <span className="heading-text">{params["dataset_name"]}</span>
        </FlexItem>
        <FlexItem className="heading">
          <a
            className="download-icon"
            href={inventoryDownloadLink}
            target="_blank"
            rel="noreferrer"
          >
            <DownloadIcon />
          </a>
          <span className="heading-text">Download tarball</span>
        </FlexItem>
      </Flex>
      <Divider component="div" className="header-separator" />
      <Sidebar>
        <SidebarPanel>
          <DrilldownMenu drillMenuItem={drillMenuItem} />
        </SidebarPanel>
        <SidebarContent>
          <div className="toc-content">
            {Object.keys(activeFile).length > 0 && (
              <List isPlain>
                <ListItem>
                  <span className="file-label">File Name:</span>
                  {activeFile.name}
                </ListItem>
                <ListItem>
                  <span className="file-label">File Size:</span>
                  {activeFile.size}
                </ListItem>

                <ListItem>
                  <span className="file-label">To view download</span>
                  <a
                    className="download-icon"
                    href={activeFile.uri}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <DownloadIcon />
                  </a>
                </ListItem>
              </List>
            )}
          </div>
        </SidebarContent>
      </Sidebar>
    </div>
  );
};

export default TableOfContent;
