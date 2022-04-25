import { Breadcrumb, BreadcrumbItem } from "@patternfly/react-core";
import React from "react";

function PathBreadCrumb({ pathList }) {
  return (
    <Breadcrumb>
      {pathList.map((path, index) => {
        return (
          <BreadcrumbItem
            key={index}
            to={path.link}
            isActive={index === pathList.length - 1 ? true : false}
          >
            {path.name}
          </BreadcrumbItem>
        );
      })}
    </Breadcrumb>
  );
}

export default PathBreadCrumb;
