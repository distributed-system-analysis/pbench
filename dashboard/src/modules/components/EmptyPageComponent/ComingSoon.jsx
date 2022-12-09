import "./index.less";

import { Button } from "@patternfly/react-core";
import React from "react";
import { useNavigate } from "react-router-dom";

const ComingSoonPage = () => {
  const navigate = useNavigate();
  return (
    <div className="comingsoon-page-container">
      <h1>
        Coming Soon<span className="dot">.</span>
      </h1>
      <Button variant="link" onClick={() => navigate("/")}>
        Go to Home
      </Button>
    </div>
  );
};

export default ComingSoonPage;
