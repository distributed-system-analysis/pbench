import React from 'react'
import {
    Bullseye,
    EmptyState,
    EmptyStateVariant,
    EmptyStateIcon,
    Title,
    EmptyStateBody,
  } from '@patternfly/react-core';
  import SearchIcon from '@patternfly/react-icons/dist/esm/icons/search-icon';

function EmptyTable() {
  return (
    // <Bullseye>
    <EmptyState variant={EmptyStateVariant.small}>
      <EmptyStateIcon icon={SearchIcon} />
      <Title headingLevel="h2" size="lg">
        No results found
      </Title>
      <EmptyStateBody>No Records Available</EmptyStateBody>
    </EmptyState>
//   </Bullseye>
  )
}

export default EmptyTable