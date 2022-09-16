import React, { useState } from "react";
import { Nav, NavItem, NavList } from "@patternfly/react-core";

const NavItems = () => {
  const [activeItem, setActiveItem] = useState("grp-1_itm-1");
  const onSelect = (result) => {
    setActiveItem(result.itemId);
  };
  return (
    <Nav onSelect={onSelect}>
      <NavList>
        <NavItem
          preventDefault
          to="#grouped-1"
          itemId="grp-1_itm-1"
          isActive={activeItem === "grp-1_itm-1"}
        >
          Dashboard
        </NavItem>
        <NavItem
          preventDefault
          to="#grouped-2"
          itemId="grp-1_itm-2"
          isActive={activeItem === "grp-1_itm-2"}
        >
          Search
        </NavItem>
        <NavItem
          preventDefault
          to="#grouped-3"
          itemId="grp-1_itm-3"
          isActive={activeItem === "grp-1_itm-3"}
        >
          Explore
        </NavItem>
      </NavList>
    </Nav>
  );
};

export default NavItems;
