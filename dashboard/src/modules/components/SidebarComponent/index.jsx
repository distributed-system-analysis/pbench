import {
  Nav,
  NavGroup,
  NavItem,
  NavList,
  PageSidebar,
} from "@patternfly/react-core";
import React, { useEffect } from "react";
import { menuOptions, menuOptionsNonLoggedIn } from "./sideMenuOptions";
import { useDispatch, useSelector } from "react-redux";
import { useLocation, useNavigate } from "react-router-dom";

import Cookies from "js-cookie";
import { setActiveItem } from "actions/sideBarActions";

const Menu = () => {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const activeItem = useSelector((state) => state.sidebar.activeMenuItem);
  const isLoggedIn = Cookies.get("isLoggedIn");
  const onSelect = (result) => {
    dispatch(setActiveItem(result.itemId));
  };

  useEffect(() => {
    if (pathname) {
      const modPathName = pathname.replace(/\/+$/, "");
      const currPath = modPathName.split("/").at(-1);

      dispatch(setActiveItem(currPath));
    }
  }, [dispatch, isLoggedIn, pathname]);
  return (
    <>
      {isLoggedIn ? (
        <Nav onSelect={onSelect}>
          {menuOptions.map((item, index) => (
            <NavGroup
              key={index}
              aria-label={item.group.title}
              title={item.group.title}
            >
              {item.submenu.map((option) => (
                <NavItem
                  preventDefault
                  onClick={() => navigate(option.link)}
                  key={option.key}
                  itemId={option.key}
                  isActive={activeItem === option.key}
                >
                  {option.name}
                </NavItem>
              ))}
            </NavGroup>
          ))}
        </Nav>
      ) : (
        <Nav onSelect={onSelect}>
          <NavList>
            {menuOptionsNonLoggedIn.map((option) => (
              <NavItem
                preventDefault
                onClick={() => navigate(option.link)}
                key={option.key}
                itemId={option.key}
                isActive={activeItem === option.key}
              >
                {option.name}
              </NavItem>
            ))}
          </NavList>
        </Nav>
      )}
    </>
  );
};

const Sidebar = () => {
  const isNavOpen = useSelector((state) => state.navOpen.isNavOpen);

  return (
    <PageSidebar nav={<Menu />} className="sidebar" isNavOpen={isNavOpen} />
  );
};

export default Sidebar;
