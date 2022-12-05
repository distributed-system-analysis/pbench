import "./index.less";

import { Button } from "@patternfly/react-core";
import React from "react";
import logo from "assets/images/page_not_found.png";
import pbenchLogo from "assets/logo/pbench_logo.svg";
import { useNavigate } from "react-router-dom";

const NoMatchingPage = () => {
  const navigate = useNavigate();
  return (
    <>
      <div className="logo-container">
        <img
          className="pbench-logo"
          onClick={() => navigate("/")}
          src={pbenchLogo}
        />
      </div>

      <div className="nomatch-container">
        <div className="main-content">
          <div className="bg-img-wrapper">
            <img className="not-found-img" alt="not found image" src={logo} />
          </div>
        </div>
        <Button variant="link" onClick={() => navigate("/")}>
          Go to Home
        </Button>
      </div>
    </>
  );
};

export default NoMatchingPage;
