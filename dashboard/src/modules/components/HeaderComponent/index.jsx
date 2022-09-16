import React, { useState } from "react";
import "./index.less";
import { useNavigate, useLocation } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
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
import {
  BarsIcon,
  ShareSquareIcon,
  QuestionCircleIcon,
} from "@patternfly/react-icons";
import pbenchLogo from "assets/logo/pbench_logo.svg";
import Cookies from "js-cookie";
import { logout } from "actions/authActions";
import { NAVBAR_CLOSE, NAVBAR_OPEN } from "actions/types";

const HeaderToolbar = () => {
  const dispatch = useDispatch();
  const loginDetails = useSelector((state) => state.userAuth.loginDetails);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const isLoggedIn = Cookies.get("isLoggedIn");

  const onDropdownSelect = (event) => {
    const type = event.target.name;
    const menuOptions = {
      profile: () => navigate("/user-profile"),
      logout: () => dispatch(logout()),
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
            {isLoggedIn ? (
              <Dropdown
                position="right"
                onSelect={onDropdownSelect}
                isOpen={isDropdownOpen}
                toggle={
                  <DropdownToggle onToggle={onDropdownToggle}>
                    {loginDetails?.username}
                  </DropdownToggle>
                }
                dropdownItems={userDropdownItems}
              />
            ) : (
              <Button
                aria-label="Login"
                className="header-login-button"
                variant={ButtonVariant.plain}
                onClick={() => navigate("/login")}
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
