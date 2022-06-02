import React from "react";
import { PageSidebar } from "@patternfly/react-core";
import NavItems from "../NavbarComponent";
import { useSelector } from "react-redux";

const Sidebar = () => {
  const isNavOpen = useSelector((state) => state.navOpen.isNavOpen);
  return (
    <PageSidebar nav={<NavItems />} className="sidebar" isNavOpen={isNavOpen} />
  );
};

export default Sidebar;
