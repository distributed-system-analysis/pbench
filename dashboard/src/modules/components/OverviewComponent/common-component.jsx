import "./index.less";

import * as CONSTANTS from "assets/constants/overviewConstants";

import {
  ActionsColumn,
  Table,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
} from "@patternfly/react-table";
import {
  Button,
  DatePicker,
  Dropdown,
  DropdownItem,
  DropdownToggle,
  Modal,
  ModalVariant,
  Pagination,
  Text,
  TextContent,
  TextInput,
  TextVariants,
} from "@patternfly/react-core";
import {
  CaretDownIcon,
  CheckIcon,
  PencilAltIcon,
  PficonTemplateIcon,
  RedoIcon,
  TimesIcon,
} from "@patternfly/react-icons";
import {
  DATASET_ACCESS,
  DATASET_UPLOADED,
  EXPIRATION_DAYS_LIMIT,
  SERVER_DELETION,
} from "assets/constants/overviewConstants";
import React, { useState } from "react";
import {
  getDatasets,
  setMetadataModal,
  updateMultipleDataset,
} from "actions/overviewActions";
import { useDispatch, useSelector } from "react-redux";

import MetadataTreeView from "./MetadataTreeComponent";
import { formatDateTime } from "utils/dateFunctions";
import { setRelayModalState } from "actions/relayActions";
import { uid } from "utils/helper";

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
        <Button
          disabled={Object.keys(endpoints).length <= 0}
          className="relay-button"
          variant="primary"
          onClick={() => dispatch(setRelayModalState(true))}
        >
          Pull dataset
        </Button>
        <Button
          variant="link"
          icon={<PficonTemplateIcon />}
          onClick={() => dispatch(setMetadataModal(true))}
        >
          Display Metadata
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
  const isDirtyRow = () => {
    return (
      props.item[CONSTANTS.IS_DIRTY_NAME] ||
      props.item[CONSTANTS.IS_DIRTY_SERVER_DELETE]
    );
  };
  return (
    <div className="pf-c-inline-edit__action pf-m-enable-editable">
      {!props.item[CONSTANTS.IS_EDIT] ? (
        <Button
          variant="plain"
          onClick={() => props.toggleEdit(props.item.resource_id, true)}
          icon={<PencilAltIcon />}
        />
      ) : (
        <div>
          <Button
            isDisabled={
              !isDirtyRow() ||
              !props.item.name ||
              props.item[CONSTANTS.NAME_VALIDATED] === CONSTANTS.ERROR
            }
            onClick={() => props.saveRowData(props.item)}
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

export const DatasetNameInput = (props) => (
  <TextInput
    validated={props.validated}
    value={props.value}
    type="text"
    onChange={props.onChange}
    aria-label="Edit Dataset name"
  />
);

export const NewRunsRow = (props) => {
  const { item, rowIndex, columnNames, isRunExpanded, setRunExpanded } = props;

  return (
    <>
      <Td
        expand={
          item.metadata
            ? {
                rowIndex,
                isExpanded: isRunExpanded(item),
                onToggle: () => setRunExpanded(item, !isRunExpanded(item)),
                expandId: "new-runs-table",
              }
            : undefined
        }
      />
      <Td
        select={{
          rowIndex,
          onSelect: (_event, isSelecting) =>
            props.onSelectRuns(item, rowIndex, isSelecting),
          isSelected: props.isRowSelected(item),
        }}
      />
      <Td dataLabel={columnNames.result}>
        {item[CONSTANTS.IS_EDIT] ? (
          <DatasetNameInput
            validated={item[CONSTANTS.NAME_VALIDATED]}
            value={item.name}
            type="text"
            onChange={props.textInputEdit}
          />
        ) : (
          item.name
        )}
      </Td>
      <Td dataLabel={columnNames.endtime}>
        {formatDateTime(item.metadata[SERVER_DELETION])}
      </Td>
      <Td
        favorites={{
          isFavorited: item.isItemFavorited,
          onFavorite: (_event, isFavoriting) =>
            props.makeFavorites(item, isFavoriting),
          rowIndex,
        }}
      />
      <Td>
        <EditRow
          item={item}
          toggleEdit={props.toggleEdit}
          saveRowData={props.saveRowData}
        />
      </Td>
      <Td isActionCell>
        {props.rowActions ? <ActionsColumn items={props.rowActions} /> : null}
      </Td>
    </>
  );
};

export const SavedRunsRow = (props) => {
  const { item, rowIndex, columnNames, rowActions } = props;
  return (
    <>
      <Td
        select={{
          rowIndex,
          onSelect: (_event, isSelecting) =>
            props.onSelectRuns(item, rowIndex, isSelecting),
          isSelected: props.isRowSelected(item),
        }}
      />
      <Td className="result_column" dataLabel={columnNames.result}>
        {item[CONSTANTS.IS_EDIT] ? (
          <DatasetNameInput
            validated={item[CONSTANTS.NAME_VALIDATED]}
            value={item.name}
            type="text"
            onChange={props.textInputEdit}
          />
        ) : (
          item.name
        )}
      </Td>
      <Td dataLabel={columnNames.endtime}>
        {formatDateTime(item.metadata[DATASET_UPLOADED])}
      </Td>
      <Td dataLabel={columnNames.scheduled}>
        {item.isEdit ? (
          <SelectDateComponent
            value={item.metadata[SERVER_DELETION]}
            onDateSelect={props.onDateSelect}
          />
        ) : (
          formatDateTime(item.metadata[SERVER_DELETION])
        )}
      </Td>
      <Td className="access">{item.metadata[DATASET_ACCESS]}</Td>
      <Td
        favorites={{
          isFavorited: item.isItemFavorited,
          onFavorite: (_event, isFavoriting) =>
            props.makeFavorites(item, isFavoriting),
          rowIndex,
        }}
      />
      <Td>
        <EditRow
          item={item}
          toggleEdit={props.toggleEdit}
          saveRowData={props.saveRowData}
        />
      </Td>
      <Td isActionCell>
        {rowActions ? <ActionsColumn items={rowActions} /> : null}
      </Td>
    </>
  );
};

export const SelectDateComponent = (props) => (
  <div className="date-picker-container">
    <DatePicker value={props.value} onChange={props.onDateSelect} />
  </div>
);

export const MetaDataModal = () => {
  const { isMetadataModalOpen } = useSelector((state) => state.overview);
  const dispatch = useDispatch();
  const handleModalToggle = () => {
    dispatch(setMetadataModal(false));
  };
  return (
    <Modal
      variant={ModalVariant.small}
      title="Display Metadata"
      isOpen={isMetadataModalOpen}
      onClose={handleModalToggle}
    >
      <MetadataTreeView />
    </Modal>
  );
};

export const MetadataRow = (props) => {
  const { checkedItems, item } = props;
  const columnNames = {
    key: "Metadata",
    value: "Value",
  };
  return (
    <Table className="box" key={uid()} aria-label="metadata-table">
      <Thead>
        <Th width={25} textCenter>
          {columnNames.key}
        </Th>
        <Th width={40}>{columnNames.value}</Th>
      </Thead>
      <Tbody>
        {checkedItems.map((attr) => {
          const levels = attr.split(CONSTANTS.KEYS_JOIN_BY);
          const showKey = attr.split(CONSTANTS.KEYS_JOIN_BY).join(".");
          const showValue = levels.reduce(
            (a, level) => a?.[level] ?? "",
            item.metadata
          );
          return (
            <>
              {showValue && showValue.constructor !== Object && (
                <Tr key={uid()}>
                  <Td className="keyClass">{showKey}</Td>
                  <Td className="valueClass">{showValue}</Td>
                </Tr>
              )}
            </>
          );
        })}
      </Tbody>
    </Table>
  );
};
