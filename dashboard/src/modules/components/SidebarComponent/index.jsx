import { Nav, NavGroup, NavItem, PageSidebar } from "@patternfly/react-core";
import React, { useState } from "react";

import { menuOptions } from "./sideMenuOptions";
import { useSelector } from "react-redux";

const Menu = () => {
  const [activeItem, setActiveItem] = useState("overview");
  const onSelect = (result) => {
    setActiveItem(result.itemId);
  };
  return (
    <Nav onSelect={onSelect}>
      {menuOptions.map((item) => {
        return (
          <NavGroup key={item.group.key} title={item.group.title}>
            {item.submenu.map((option) => {
              return (
                <NavItem
                  to={option.link}
                  key={option.key}
                  itemId={option.key}
                  isActive={activeItem === option.key}
                >
                  {option.name}
                </NavItem>
              );
            })}
          </NavGroup>
        );
      })}
    </Nav>
  );
};
const Sidebar = () => {
  const isNavOpen = useSelector((state) => state.navOpen.isNavOpen);
  return (
    <PageSidebar nav={<Menu />} className="sidebar" isNavOpen={isNavOpen} />
  );
};

export default Sidebar;
