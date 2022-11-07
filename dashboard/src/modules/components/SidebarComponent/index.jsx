import { Nav, NavGroup, NavItem, PageSidebar } from "@patternfly/react-core";
import { useDispatch, useSelector } from "react-redux";

import React from "react";
import { menuOptions } from "./sideMenuOptions";
import { setActiveItem } from "actions/sideBarActions";

const Menu = () => {
  const dispatch = useDispatch();
  const onSelect = (result) => {
    dispatch(setActiveItem(result.itemId));
  };
  const activeItem = useSelector((state) => state.sidebar.activeMenuItem);

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
