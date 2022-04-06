import { Text, TextContent,TextVariants } from '@patternfly/react-core'
import React from 'react'

function Heading({headingTitle}) {
  return (
    <TextContent>
        <Text component={TextVariants.h1} style={{fontWeight:'800',marginBottom:'2vh',marginTop:'2vh'}}>{headingTitle}</Text>
    </TextContent>
  )
}

export default Heading