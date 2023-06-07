import { Button, Tooltip } from "@patternfly/react-core";
import React, { useState } from "react";

import { CopyIcon } from "@patternfly/react-icons";
import { SHOW_COPIED_TEXT_MS } from "assets/constants/copyTextConstants";

const ClipboardCopy = ({ copyText }) => {
  const [isCopied, setIsCopied] = useState(false);

  /* Funcion has to be rewritten by removing document.execCommand() on upgrading to HTTPS */
  const copyTextToClipboard = async (text) =>
    "clipboard" in navigator
      ? await navigator.clipboard.writeText(text)
      : document.execCommand("copy", true, text);

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
