import { Button, Tooltip } from "@patternfly/react-core";
import React, { useState } from "react";

import { CopyIcon } from "@patternfly/react-icons";
import { SHOW_COPIED_TEXT_MS } from "assets/constants/copyTextConstants";

const ClipboardCopy = ({ copyText }) => {
  const [isCopied, setIsCopied] = useState(false);

  const copyTextToClipboard = async (text) => {
    if ("clipboard" in navigator) {
      return await navigator.clipboard.writeText(text);
    } else {
      return document.execCommand("copy", true, text);
    }
  };

  // onClick handler function for the copy button
  const handleCopyClick = () => {
    // Asynchronously call copyTextToClipboard
    copyTextToClipboard(copyText)
      .then(() => {
        // If successful, update the isCopied state value
        setIsCopied(true);
        setTimeout(() => {
          setIsCopied(false);
        }, SHOW_COPIED_TEXT_MS);
      })
      .catch((err) => {
        console.log(err);
      });
  };

  return (
    <div className="key-cell-wrapper">
      <div className="key-cell">{copyText}</div>
      <Tooltip
        aria="none"
        aria-live="polite"
        content={isCopied ? "Copied" : "Copy to clipboard"}
      >
        <Button
          variant="plain"
          className="copy-icon"
          onClick={() => handleCopyClick(copyText)}
        >
          <CopyIcon />
        </Button>
      </Tooltip>
    </div>
  );
};

export default ClipboardCopy;
