import {
  EmptyState,
  EmptyStateBody,
  EmptyStateIcon,
  EmptyStateVariant,
  Title,
} from "@patternfly/react-core";

import CubesIcon from "@patternfly/react-icons/dist/esm/icons/cubes-icon";
import React from "react";

export const ComingSoonComponent = () => (
  <EmptyState variant={EmptyStateVariant.xl}>
    <EmptyStateIcon icon={CubesIcon} />
    <Title headingLevel="h5" size="4xl">
      Coming Soon
    </Title>
    <EmptyStateBody></EmptyStateBody>
  </EmptyState>
);
