import { Breadcrumb, BreadcrumbItem } from "@patternfly/react-core";
import React from "react";

function PathBreadCrumb({ pathList }) {
  return (
    <Breadcrumb>
      {pathList.map((value, index) => {
        if (index === pathList.length - 1)
          return (
            <BreadcrumbItem key={index} to="#" isActive>
              {value}
            </BreadcrumbItem>
          );
        else
          return (
            <BreadcrumbItem key={index} to="#">
              {value}
            </BreadcrumbItem>
          );
      })}
    </Breadcrumb>
  );
}

export default PathBreadCrumb;
