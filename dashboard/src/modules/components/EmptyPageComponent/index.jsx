import {
  Button,
  EmptyState,
  EmptyStateBody,
  EmptyStateIcon,
  EmptyStateVariant,
  Title,
} from "@patternfly/react-core";

import CubesIcon from "@patternfly/react-icons/dist/esm/icons/cubes-icon";
import React from "react";
import { useNavigate } from "react-router-dom";

const EmptyPage = (props) => {
  const navigate = useNavigate();
  return (
    <EmptyState variant={EmptyStateVariant.xl}>
      <EmptyStateIcon icon={CubesIcon} />
      <Title headingLevel="h5" size="4xl">
        {props.text}
      </Title>
      <EmptyStateBody>
        <Button type="primary" onClick={() => navigate("/")}>
          Go to Home
        </Button>
      </EmptyStateBody>
    </EmptyState>
  );
};

export default EmptyPage;
