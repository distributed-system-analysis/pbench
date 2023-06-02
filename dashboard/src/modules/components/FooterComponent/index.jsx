import "./index.less";

import React from "react";
import { useSelector } from "react-redux";

const Footer = () => {
  const { endpoints } = useSelector((state) => state.apiEndpoint);
  const versionNumber = endpoints?.identification
    ?.split(" ")
    .slice(-1)
    .join("");
  return (
    <div className="footer-container">
      Version @ <span> {versionNumber}</span>
    </div>
  );
};

export default Footer;
