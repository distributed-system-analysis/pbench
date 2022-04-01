import React, { useState } from "react";
import "./index.less";
import { useDispatch } from "react-redux";
import {
  TextContent,
  TextVariants,
  Text,
  Button,
  Dropdown,
  DropdownToggle,
  DropdownItem,
  Pagination,
} from "@patternfly/react-core";
import { RedoIcon, CaretDownIcon } from "@patternfly/react-icons";
import { updateMultipleDataset } from "actions/overviewActions";

export const Heading = (props) => {
  return (
    <TextContent>
      <Text component={TextVariants.h2}> {props.title} </Text>
    </TextContent>
  );
};

export const Separator = () => {
  return <div className="separator" />;
};

export const NoExpiringRuns = () => {
  return (
    <>
      <TextContent className="no-runs-wrapper">
        <Text component={TextVariants.h3}> You have no runs expiring soon</Text>
        <Text component={TextVariants.p}>
          Runs that have expiration date within next 10days will appear here.
          These runs will be automatically removed from the system if left
          unacknowledged. <Button variant="link">Learn More.</Button>
        </Text>
      </TextContent>
    </>
  );
};

export const NewRunsHeading = () => {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dispatch = useDispatch();

  const actions = [
    {
      name: "Save",
      key: "save",
    },
    {
      name: "Mark read",
      key: "read",
    },
    {
      name: " Mark favorited",
      key: "favorite",
    },
    {
      name: "Delete",
      key: "delete",
    },
  ];
  const dropdownItems = actions.map((item) => {
    return (
      <DropdownItem
        key={item.key}
        onClick={() => dispatch(updateMultipleDataset(item.key))}
      >
        {item.name}
      </DropdownItem>
    );
  });

  const onToggle = () => {
    setDropdownOpen(!dropdownOpen);
  };
  const onSelect = () => {
    setDropdownOpen(!dropdownOpen);
  };
  return (
    <div className="newruns-heading-container">
      <Heading title="New and unmanaged runs" />
      <div>
        <Button variant="link" icon={<RedoIcon />}>
          Refresh results
        </Button>
        <Dropdown
          onSelect={onSelect}
          toggle={
            <DropdownToggle
              onToggle={onToggle}
              toggleIndicator={CaretDownIcon}
              isPrimary
              id="manage-runs-toggle"
            >
              Manage
            </DropdownToggle>
          }
          isOpen={dropdownOpen}
          dropdownItems={dropdownItems}
        />
      </div>
    </div>
  );
};

export const RenderPagination = (props) => {
  const {
    page,
    perPage,
    onSetPage,
    items,
    setperpage,
    perPageOptions,
    onPerPageSelect,
  } = props;

  return (
    <Pagination
      isCompact
      itemCount={items}
      page={page}
      onSetPage={onSetPage}
      perPage={perPage}
      variant={"bottom"}
      setperpage={setperpage}
      perPageOptions={perPageOptions}
      onPerPageSelect={onPerPageSelect}
    />
  );
};
