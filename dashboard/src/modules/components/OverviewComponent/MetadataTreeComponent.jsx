import "./index.less";

import { mapTree, onCheck } from "actions/metadataTreeActions";
import { useDispatch, useSelector } from "react-redux";

import React from "react";
import { TreeView } from "@patternfly/react-core";

const MetadataTreeView = () => {
  const { treeData } = useSelector((state) => state.overview);
  const dispatch = useDispatch();
  const onCheckHandler = (evt, treeViewItem, dataType) => {
    dispatch(onCheck(evt, treeViewItem, dataType));
  };
  return (
    <div className="treeview-container">
      {treeData &&
        treeData.length > 0 &&
        treeData.map((item) => {
          const mapped = item.options.map((item) => mapTree(item));
          return (
            <div key={item.title}>
              <h1 className="title">{item.title}</h1>
              <TreeView
                data={mapped}
                hasChecks
                onCheck={(evt, treeItem) =>
                  onCheckHandler(evt, treeItem, item.title)
                }
              />
            </div>
          );
        })}
    </div>
  );
};

export default MetadataTreeView;
