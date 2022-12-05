import "./index.less";

import React from "react";
import { Spinner } from "@patternfly/react-core";
import { useSelector } from "react-redux";

const LoadingComponent = ({ children }) => {
  const isLoading = useSelector((state) => state.loading.isLoading);
  const parentClass = isLoading ? "main-with-spinner" : "";
  return (
    <div className={`main-page-container ${parentClass}`}>
      {children}
      {isLoading && (
        <div className="spinner-container">
          <Spinner size="md" isSVG className="spinner" />
        </div>
      )}
    </div>
  );
};

export default LoadingComponent;
