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
import { useKeycloak } from "@react-keycloak/web";
import { setActiveItem } from "actions/sideBarActions";

const MenuItem = ({ data, activeItem }) => {
  const navigate = useNavigate();
  return data.map((option) => (
    <NavItem
      preventDefault
      onClick={() => navigate(option.link)}
      key={option.key}
      itemId={option.key}
      isActive={activeItem === option.key}
    >
      {option.name}
    </NavItem>
  ));
};

const Menu = () => {
  const dispatch = useDispatch();

  const { pathname } = useLocation();

  const activeItem = useSelector((state) => state.sidebar.activeMenuItem);
  const { keycloak } = useKeycloak();
  const onSelect = (result) => {
    dispatch(setActiveItem(result.itemId));
  };

  useEffect(() => {
    if (pathname) {
      const currPath = pathname.replace(/^.*[/]([^/]+)[/]*$/, "$1");

      dispatch(setActiveItem(currPath));
    }
  }, [dispatch, pathname]);

  return (
    <Nav onSelect={onSelect}>
      {keycloak.authenticated ? (
        menuOptions.map((item, index) => (
          <NavGroup
            key={index}
            aria-label={item.group.title}
            title={item.group.title}
          >
            <MenuItem data={item.submenu} activeItem={activeItem} />
          </NavGroup>
        ))
      ) : (
        <NavList>
          <MenuItem data={menuOptionsNonLoggedIn} activeItem={activeItem} />
        </NavList>
      )}
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
