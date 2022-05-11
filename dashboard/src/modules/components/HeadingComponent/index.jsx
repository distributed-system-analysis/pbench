import { Text, TextContent, TextVariants } from "@patternfly/react-core";
import "./index.css"
import React from "react";

function Heading({ headingTitle }) {
  return (
    <TextContent>
      <Text
        component={TextVariants.h1}
        className="publicDataPageTitle"
      >
        {headingTitle}
      </Text>
    </TextContent>
  );
}

export default Heading;
