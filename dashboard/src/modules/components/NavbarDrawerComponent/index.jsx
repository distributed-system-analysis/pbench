import React from "react";
import {
  Masthead,
  MastheadToggle,
  PageToggleButton,
} from "@patternfly/react-core";
import BarsIcon from "@patternfly/react-icons/dist/js/icons/bars-icon";
import { useDispatch, useSelector } from "react-redux";
import { NAVBAR_CLOSE, NAVBAR_OPEN } from "../../../actions/types";

const NavbarDrawer = () => {
  const isNavOpen = useSelector((state) => state.navOpen.isNavOpen);
  const dispatch = useDispatch();
  const onNavToggle = () => {
    const navAction = isNavOpen
      ? { type: NAVBAR_CLOSE }
      : { type: NAVBAR_OPEN };
    dispatch(navAction);
  };
  return (
    <Masthead id="basic">
      <MastheadToggle>
        <PageToggleButton isNavOpen={isNavOpen} onNavToggle={onNavToggle}>
          <BarsIcon />
        </PageToggleButton>
      </MastheadToggle>
    </Masthead>
  );
};

export default NavbarDrawer;
