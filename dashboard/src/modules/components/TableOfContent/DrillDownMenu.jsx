import { FolderIcon, FolderOpenIcon } from "@patternfly/react-icons";
import React, { useState } from "react";

import { TreeView } from "@patternfly/react-core";
import { useSelector } from "react-redux";

const DrilldownMenu = (props) => {
  const { drillMenuData } = useSelector((state) => state.toc);
  const [activeItems, setActiveItems] = useState([]);
  const onSelect = (_evt, item) => {
    setActiveItems([item]);
    props.drillMenuItem(item);
  };

  return (
    <div className="drilldownMenu-container">
      {drillMenuData?.length > 0 && (
        <TreeView
          data={drillMenuData}
          activeItems={activeItems}
          onSelect={onSelect}
          icon={<FolderIcon />}
          expandedIcon={<FolderOpenIcon />}
        />
      )}
    </div>
  );
};

export default DrilldownMenu;
