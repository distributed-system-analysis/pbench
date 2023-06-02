import "./index.less";

import React from "react";
import { useSelector } from "react-redux";

const Footer = () => {
  const { endpoints } = useSelector((state) => state.apiEndpoint);

  return (
    <div className="footer-container">
      Version @ <span> {endpoints?.identification}</span>
    </div>
  );
};

export default Footer;
