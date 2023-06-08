import {
  TableComposable,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
} from "@patternfly/react-table";

import ClipboardCopy from "modules/components/ProfileComponent/ClipboardCopy";
import React from "react";

const DatasetTable = () => {
  const data = [
    {
      uri: "https://relay.example.com/52adfdd3dbf2a87ed6c1c41a1ce278290064b0455f585149b3dadbe5a0b62f44",
      name: "fio_rw_2018.02.01T22.40.57.tar.xz",
      key: 1,
    },
    {
      uri: "https://relay.example.com/52adfdd3dbf2a87ed6c1c41a1ce278290064b0455f585149b3dadbe5a0b62f44",
      name: "fio_rw_2018.02.01T22.40.57.tar.xz",
      key: 2,
    },
    {
      uri: "https://relay.example.com/52adfdd3dbf2a87ed6c1c41a1ce278290064b0455f585149b3dadbe5a0b62f44",
      name: "fio_rw_2018.02.01T22.40.57.tar.xz",
      key: 3,
    },
    {
      uri: "https://relay.example.com/52adfdd3dbf2a87ed6c1c41a1ce278290064b0455f585149b3dadbe5a0b62f44",
      name: "fio_rw_2018.02.01T22.40.57.tar.xz",
      key: 4,
    },
  ];
  const columnNames = {
    uri: "Dataset URI",
    name: "Name",
  };

  return (
    <TableComposable aria-label="Relay Dataset table">
      <Thead>
        <Tr>
          <Th width={10}>{columnNames.name}</Th>
          <Th width={20}>{columnNames.uri}</Th>
        </Tr>
      </Thead>
      <Tbody className="dataset-table-body">
        {data.map((item) => (
          <Tr key={item.key}>
            <Td dataLabel={columnNames.name}>{item.name}</Td>

            <Td dataLabel={columnNames.uri}>
              <ClipboardCopy copyText={item.uri} />
            </Td>
          </Tr>
        ))}
      </Tbody>
    </TableComposable>
  );
};

export default DatasetTable;
