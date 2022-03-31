import React from 'react';
import { Masthead, MastheadToggle, MastheadMain,MastheadContent, Button } from '@patternfly/react-core';
import BarsIcon from '@patternfly/react-icons/dist/js/icons/bars-icon';
import './navigationDrawer.css'
import UserUtilities from '../userUtilities/UserUtilities';
const NavigationDrawer = ({accountName,isUserLogin}) => (
  
  <Masthead id="basic">
    <MastheadToggle>
      <Button variant="plain" onClick={() => {}} aria-label="Global navigation">
        <BarsIcon />
      </Button>
    </MastheadToggle>
    <MastheadMain>
      <MastheadContent>
        <UserUtilities accountName={accountName} isUserLogin={isUserLogin}/>
      </MastheadContent>
    </MastheadMain>
  </Masthead>
)
export default NavigationDrawer