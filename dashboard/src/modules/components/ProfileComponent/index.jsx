import React from "react";
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
  isValidDate,
} from "@patternfly/react-core";
import { KeyIcon, UserAltIcon } from "@patternfly/react-icons";
import "./index.less";
import avatar from "assets/images/avatar.jpg";
import { useKeycloak } from "@react-keycloak/web";

const ProfileComponent = () => {
  const { keycloak } = useKeycloak();

  const formatDate = (date) => {
    const registerDate = new Date(date);
    return isValidDate(registerDate)
      ? registerDate.toLocaleDateString()
      : "----";
  };
  return (
    <div className={"profileDiv"}>
      <TextContent>
        <Text component={TextVariants.h2}>User Profile</Text>
      </TextContent>
      <div className="headerDiv">
        <Grid hasGutter>
          <GridItem span={8}>
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
          </GridItem>
          <GridItem span={4}>
            <Card className="card">
              <CardBody>
                <div className="subHeader settings-wrapper">
                  <KeyIcon />
                  <span className="subHeader">Settings</span>
                </div>
                <Grid>
                  <GridItem span={12} className="subCardDiv">
                    <TextContent>
                      {/* TODO: How to handle account creation date */}
                      <span>Account creation Date</span>
                      <Text component={TextVariants.h4}>
                        {formatDate("MM/DD/YYYY")}
                      </Text>
                    </TextContent>
                  </GridItem>
                </Grid>
              </CardBody>
            </Card>
          </GridItem>
        </Grid>
      </div>
    </div>
  );
};

export default ProfileComponent;
