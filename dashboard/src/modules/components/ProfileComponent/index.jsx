import "./index.less";

import {
  Card,
  CardBody,
  Grid,
  GridItem,
  Level,
  LevelItem,
  Text,
  TextContent,
  TextVariants,
} from "@patternfly/react-core";

import KeyManagementComponent from "./KeyManagement";
import React from "react";
import { UserAltIcon } from "@patternfly/react-icons";
import avatar from "assets/images/avatar.jpg";
import { useKeycloak } from "@react-keycloak/web";

const ProfileComponent = () => {
  const { keycloak } = useKeycloak();

  return (
    <div className={"profileDiv"}>
      <Grid>
        <GridItem span={1} />
        <GridItem span={10}>
          <TextContent>
            <Text component={TextVariants.h2}>User Profile</Text>
          </TextContent>
        </GridItem>
        <GridItem span={1} />
      </Grid>

      <div className="headerDiv">
        <Grid hasGutter>
          <GridItem span={1} />
          <GridItem span={10}>
            <Card className="card">
              <CardBody>
                <Level className="levelCard">
                  <LevelItem>
                    <UserAltIcon />
                    <span className="subHeader">Account Details</span>
                  </LevelItem>
                </Level>
                <div className="detailsDiv">
                  <Grid span={12}>
                    <GridItem md={3} lg={4} className="item-container">
                      <div className="item-header">Profile Picture</div>
                      <div className="avatarDiv">
                        <img src={avatar} alt="avatar" className="avatar" />
                      </div>
                    </GridItem>
                    <GridItem md={4} lg={4} className="item-container">
                      <div className="item-header">First Name</div>
                      {
                        <TextContent>
                          <Text component={TextVariants.h5}>
                            {keycloak.tokenParsed?.given_name
                              ? keycloak.tokenParsed.given_name
                              : ""}
                          </Text>
                        </TextContent>
                      }
                    </GridItem>
                    <GridItem md={5} lg={4} className="item-container">
                      <div className="item-header">Last Name</div>
                      {
                        <TextContent>
                          <Text component={TextVariants.h5}>
                            {keycloak.tokenParsed?.family_name
                              ? keycloak.tokenParsed.family_name
                              : ""}
                          </Text>
                        </TextContent>
                      }
                    </GridItem>
                  </Grid>
                  <Grid span={12}>
                    <GridItem md={6} lg={4} className="item-container">
                      <div className="item-header">User Name</div>
                      {
                        <TextContent>
                          <Text component={TextVariants.h5}>
                            {keycloak.tokenParsed?.preferred_username
                              ? keycloak.tokenParsed.preferred_username
                              : ""}
                          </Text>
                        </TextContent>
                      }
                    </GridItem>
                    <GridItem md={6} lg={4} className="item-container">
                      <div className="item-header">Email</div>
                      {
                        <TextContent>
                          <Text component={TextVariants.h5}>
                            {keycloak.tokenParsed?.email
                              ? keycloak.tokenParsed.email
                              : ""}
                          </Text>
                        </TextContent>
                      }
                    </GridItem>
                  </Grid>
                  {<></>}
                </div>
              </CardBody>
            </Card>
            <GridItem span={8}>
              <KeyManagementComponent />
            </GridItem>
          </GridItem>
          <GridItem span={1} />
        </Grid>
      </div>
    </div>
  );
};

export default ProfileComponent;
