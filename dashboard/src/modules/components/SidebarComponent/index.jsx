import { Nav, NavGroup, NavItem, PageSidebar } from "@patternfly/react-core";
import React, { useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";
import { useLocation, useNavigate } from "react-router-dom";

import { menuOptions } from "./sideMenuOptions";
import { setActiveItem } from "actions/sideBarActions";

const Menu = () => {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const activeItem = useSelector((state) => state.sidebar.activeMenuItem);
  const onSelect = (result) => {
    dispatch(setActiveItem(result.itemId));
  };

  useEffect(() => {
    if (pathname) {
      const currPath = pathname.split("/").at(-1);
      dispatch(setActiveItem(currPath));
    }
  }, [dispatch, pathname]);
  return (
    <Nav onSelect={onSelect}>
      {menuOptions.map((item, index) => {
        return (
          <NavGroup
            key={index}
            aria-label={item.group.title}
            title={item.group.title}
          >
            {item.submenu.map((option) => {
              return (
                <NavItem
                  preventDefault
                  onClick={() => navigate(option.link)}
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
