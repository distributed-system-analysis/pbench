import "./index.less";

import {
  Button,
  Dropdown,
  DropdownItem,
  DropdownToggle,
  Pagination,
  Text,
  TextContent,
  TextVariants,
} from "@patternfly/react-core";
import {
  CaretDownIcon,
  CheckIcon,
  PencilAltIcon,
  RedoIcon,
  TimesIcon,
} from "@patternfly/react-icons";
import React, { useState } from "react";
import { getDatasets, updateMultipleDataset } from "actions/overviewActions";
import { useDispatch, useSelector } from "react-redux";

import { EXPIRATION_DAYS_LIMIT } from "assets/constants/overviewConstants";
import { TextInput } from "@patternfly/react-core";

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
          Runs that have expiration date within next {EXPIRATION_DAYS_LIMIT}{" "}
          days will appear here. These runs will be automatically removed from{" "}
          the system if left unacknowledged.
          <Button variant="link">Learn More.</Button>
        </Text>
      </TextContent>
    </>
  );
};

const actions = [
  {
    name: "Save",
    key: "save",
    value: true,
  },
  {
    name: "Mark read",
    key: "read",
    value: true,
  },
  {
    name: "Mark unread",
    key: "read",
    value: false,
  },
  {
    name: " Mark favorited",
    key: "favorite",
    value: true,
  },
  {
    name: " Mark unfavorited",
    key: "favorite",
    value: false,
  },
  {
    name: "Delete",
    key: "delete",
    value: true,
  },
];

export const NewRunsHeading = () => {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dispatch = useDispatch();
  const { endpoints } = useSelector((state) => state.apiEndpoint);
  const { selectedRuns } = useSelector((state) => state.overview);
  const dropdownItems = actions.map((item) => {
    return (
      <DropdownItem
        key={item.key}
        onClick={() => dispatch(updateMultipleDataset(item.key, item.value))}
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
      <div>
        <Button
          variant="link"
          disabled={Object.keys(endpoints).length <= 0}
          icon={<RedoIcon />}
          onClick={() => dispatch(getDatasets())}
        >
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
              isDisabled={selectedRuns.length <= 0}
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

export const EditRow = (props) => {
  return (
    <div className="pf-c-inline-edit__action pf-m-enable-editable">
      {!props.item.isEdit ? (
        <Button
          variant="plain"
          onClick={() => props.toggleEdit(props.item.resource_id, true)}
          icon={<PencilAltIcon />}
        />
      ) : (
        <div>
          <Button
            isDisabled={
              !props.item.isDirty ||
              !!!props.item.name ||
              props.item.name_validated === "error"
            }
            onClick={() =>
              props.saveRowData("datasetName", props.item, props.item.name)
            }
            variant="plain"
            icon={<CheckIcon />}
          />
          <Button
            variant="plain"
            onClick={() => props.toggleEdit(props.item.resource_id, false)}
            icon={<TimesIcon />}
          />
        </div>
      )}
    </div>
  );
};

export const DatasetNameInput = (props) => {
  return (
    <TextInput
      validated={props.validated}
      value={props.value}
      type="text"
      onChange={props.onChange}
      aria-label="Edit Dataset name"
    />
  );
};
