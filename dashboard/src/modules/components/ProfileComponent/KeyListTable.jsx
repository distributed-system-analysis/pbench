import { Button, ClipboardCopy } from "@patternfly/react-core";
import {
  TableComposable,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
} from "@patternfly/react-table";
import { useDispatch, useSelector } from "react-redux";

import React from "react";
import { TrashIcon } from "@patternfly/react-icons";
import { deleteAPIKey } from "actions/keyManagementActions";
import { formatDateTime } from "utils/dateFunctions";

const KeyListTable = () => {
  const dispatch = useDispatch();
  const keyList = useSelector((state) => state.keyManagement.keyList);
  const columnNames = {
    label: "Label",
    created: "Created Date & Time",
    key: "API key",
  };

  const deleteKey = (id) => {
    dispatch(deleteAPIKey(id));
  };

  return (
    <TableComposable aria-label="key list table" isStriped>
      <Thead>
        <Tr>
          <Th width={10}>{columnNames.label}</Th>
          <Th width={20}>{columnNames.created}</Th>
          <Th width={20}>{columnNames.key}</Th>
          <Th width={5}></Th>
        </Tr>
      </Thead>
      <Tbody className="keylist-table-body">
        {keyList.map((item) => (
          <Tr key={item.key}>
            <Td dataLabel={columnNames.label}>{item.label}</Td>
            <Td dataLabel={columnNames.created}>
              {formatDateTime(item.created)}
            </Td>
            <Td dataLabel={columnNames.key} className="key-cell">
              <ClipboardCopy
                hoverTip="Copy API key"
                clickTip="Copied"
                variant="plain"
              >
                {item.key}
              </ClipboardCopy>
            </Td>

            <Td className="delete-icon-cell">
              <Button
                variant="plain"
                aria-label="Delete Action"
                onClick={() => deleteKey(item.id)}
              >
                <TrashIcon />
              </Button>
            </Td>
          </Tr>
        ))}
      </Tbody>
    </TableComposable>
  );
};

export default KeyListTable;
