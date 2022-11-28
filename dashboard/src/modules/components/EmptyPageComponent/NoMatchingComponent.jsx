import "./index.less";

import { Button } from "@patternfly/react-core";
import React from "react";
import { useNavigate } from "react-router-dom";

const NoMatchingComponent = () => {
  const navigate = useNavigate();
  return (
    <div className="nomatch-container">
      <div className="main-content">
        <div className="bg-img-wrapper" />
        <p className="not-found-text">
          The page you are looking for not available!
        </p>
      </div>

      <Button variant="link" onClick={() => navigate("/")}>
        Go to Home
      </Button>
    </div>
  );
};

export default NoMatchingComponent;
