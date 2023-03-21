import React from "react";
import { useSelector } from "react-redux";
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

const ProfileComponent = () => {
  const user = useSelector((state) => state.userProfile.userDetails);

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
                      {(
                        <TextContent>
                          <Text component={TextVariants.h5}>
                            {user?.first_name}
                          </Text>
                        </TextContent>
                      )}
                    </GridItem>
                    <GridItem md={5} lg={4} className="item-container">
                      <div className="item-header">Last Name</div>
                      {(
                        <TextContent>
                          <Text component={TextVariants.h5}>
                            {user?.last_name}
                          </Text>
                        </TextContent>
                      )}
                    </GridItem>
                  </Grid>
                  <Grid span={12}>
                    <GridItem md={6} lg={4} className="item-container">
                      <div className="item-header">User Name</div>
                      {(
                        <TextContent>
                          <Text component={TextVariants.h5}>
                            {user?.username}
                          </Text>
                        </TextContent>
                      )}
                    </GridItem>
                    <GridItem md={6} lg={4} className="item-container">
                      <div className="item-header">Email</div>
                      {(
                        <TextContent>
                          <Text component={TextVariants.h5}>{user?.email}</Text>
                        </TextContent>
                      )}
                    </GridItem>
                  </Grid>
                  {(
                    <></>
                  )}
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
                      <span>Account creation Date</span>
                      <Text component={TextVariants.h4}>
                        {formatDate(user?.registered_on)}
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
