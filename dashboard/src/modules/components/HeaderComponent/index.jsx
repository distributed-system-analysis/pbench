import "./index.less";

import * as APP_ROUTES from "utils/routeConstants";

import {
  BarsIcon,
  QuestionCircleIcon,
  ShareSquareIcon,
} from "@patternfly/react-icons";
import {
  Brand,
  Button,
  ButtonVariant,
  Dropdown,
  DropdownGroup,
  DropdownItem,
  DropdownToggle,
  Masthead,
  MastheadBrand,
  MastheadContent,
  MastheadMain,
  MastheadToggle,
  PageToggleButton,
  Toolbar,
  ToolbarContent,
  ToolbarGroup,
  ToolbarItem,
} from "@patternfly/react-core";
import { NAVBAR_CLOSE, NAVBAR_OPEN } from "actions/types";
import React, { useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { useLocation, useNavigate } from "react-router-dom";

import { sessionLogout } from "actions/authActions";
import pbenchLogo from "assets/logo/pbench_logo.svg";
import { useKeycloak } from "@react-keycloak/web";
import { movePage } from "actions/authActions";

const HeaderToolbar = () => {
  const dispatch = useDispatch();
  const { keycloak } = useKeycloak();
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const navigatePage = (toPage) => {
    dispatch(movePage(toPage, navigate));
  };

  const onDropdownSelect = (event) => {
    const type = event.target.name;
    const menuOptions = {
      profile: () => navigate(APP_ROUTES.USER_PROFILE),
      logout: () => dispatch(sessionLogout()),
    };
    const action = menuOptions[type];
    if (action) {
      action();
    }
    setIsDropdownOpen(false);
  };
  const onDropdownToggle = () => {
    setIsDropdownOpen(!isDropdownOpen);
  };
  const userDropdownItems = [
    <DropdownGroup key="header-dropdown">
      <DropdownItem
        name="profile"
        key="header-dropdown profile"
        autoFocus={pathname.includes("user-profile")}
      >
        My profile
      </DropdownItem>
      <DropdownItem name="logout" key="header-dropdown logout">
        Logout
      </DropdownItem>
    </DropdownGroup>,
  ];
  return (
    <Toolbar id="toolbar" isFullHeight isStatic>
      <ToolbarContent>
        <ToolbarGroup
          variant="icon-button-group"
          alignment={{ default: "alignRight" }}
          spacer={{ default: "spacerNone", md: "spacerMd" }}
        >
          <ToolbarItem>
            <Button aria-label="Share" variant={ButtonVariant.plain}>
              <ShareSquareIcon />
            </Button>
          </ToolbarItem>
          <ToolbarItem>
            <Button aria-label="Help" variant={ButtonVariant.plain}>
              <QuestionCircleIcon />
            </Button>
          </ToolbarItem>
          <ToolbarItem>
            {keycloak.authenticated ? (
              <Dropdown
                position="right"
                onSelect={onDropdownSelect}
                isOpen={isDropdownOpen}
                toggle={
                  <DropdownToggle onToggle={onDropdownToggle}>
                    {keycloak.tokenParsed?.preferred_username}
                  </DropdownToggle>
                }
                dropdownItems={userDropdownItems}
              />
            ) : (
              <Button
                aria-label="Login"
                className="header-login-button"
                variant={ButtonVariant.plain}
                onClick={() => navigatePage(APP_ROUTES.AUTH)}
              >
                Login
              </Button>
            )}
          </ToolbarItem>
        </ToolbarGroup>
      </ToolbarContent>
    </Toolbar>
  );
};
const HeaderComponent = () => {
  const dispatch = useDispatch();
  const isNavOpen = useSelector((state) => state.navOpen.isNavOpen);

  const onNavToggle = () => {
    dispatch({ type: isNavOpen ? NAVBAR_CLOSE : NAVBAR_OPEN });
  };

  return (
    <Masthead className="main-header">
      <MastheadToggle>
        <PageToggleButton
          variant="plain"
          aria-label="Side menu navigation"
          isNavOpen={isNavOpen}
          onNavToggle={onNavToggle}
        >
          <BarsIcon />
        </PageToggleButton>
      </MastheadToggle>
      <MastheadMain>
        <MastheadBrand>
          <Brand src={pbenchLogo} className="header-logo" alt="pbench Logo" />
        </MastheadBrand>
      </MastheadMain>
      <MastheadContent>
        <HeaderToolbar />
      </MastheadContent>
    </Masthead>
  );
};

export default HeaderComponent;
