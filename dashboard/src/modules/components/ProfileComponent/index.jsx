import React, { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import {
  TextContent,
  Text,
  TextVariants,
  Grid,
  GridItem,
  Card,
  Level,
  LevelItem,
  Button,
  TextInput,
  CardBody,
  isValidDate,
} from "@patternfly/react-core";
import { UserAltIcon, PencilAltIcon, KeyIcon } from "@patternfly/react-icons";
import "./index.less";
import avatar from "assets/images/avatar.jpg";
import {
  getProfileDetails,
  updateUserDetails,
  sendForUpdate,
  resetUserDetails,
} from "actions/profileActions";

const ProfileComponent = () => {
  const [editView, setEditView] = useState(false);
  const dispatch = useDispatch();

  const user = useSelector((state) => state.userProfile.userDetails);
  const loginDetails = useSelector((state) => state.userAuth.loginDetails);
  const { endpoints } = useSelector((state) => state.apiEndpoint);

  const isUserDetailsUpdated = useSelector(
    (state) => state.userProfile.isUserDetailsUpdated
  );

  const edit = () => {
    if (editView) {
      dispatch(resetUserDetails());
    }
    setEditView(!editView);
  };
  const saveEdit = () => {
    dispatch(sendForUpdate());
    setEditView(false);
  };
  useEffect(() => {
    if (loginDetails?.username && Object.keys(endpoints).length > 0) {
      dispatch(getProfileDetails());
    }
  }, [dispatch, loginDetails?.username, endpoints]);

  const formatDate = (date) => {
    const registerDate = new Date(date);
    return isValidDate(registerDate)
      ? registerDate.toLocaleDateString()
      : "----";
  };
  const handleInputChange = (value, name) => {
    dispatch(updateUserDetails(value, name));
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
                  <Button
                    variant="link"
                    icon={<PencilAltIcon />}
                    onClick={edit}
                    isDisabled={editView}
                  >
                    Edit
                  </Button>
                  <Grid span={12}>
                    <GridItem md={3} lg={4} className="item-container">
                      <div className="item-header">Profile Picture</div>
                      <div className="avatarDiv">
                        <img src={avatar} alt="avatar" className="avatar" />
                      </div>
                    </GridItem>
                    <GridItem md={4} lg={4} className="item-container">
                      <div className="item-header">First Name</div>
                      {editView ? (
                        <TextInput
                          placeholder={user?.first_name}
                          type="text"
                          aria-label="first name"
                          className="editInput"
                          name="first_name"
                          value={user?.first_name}
                          onChange={(val) =>
                            handleInputChange(val, "first_name")
                          }
                        />
                      ) : (
                        <TextContent>
                          <Text component={TextVariants.h5}>
                            {user?.first_name}
                          </Text>
                        </TextContent>
                      )}
                    </GridItem>
                    <GridItem md={5} lg={4} className="item-container">
                      <div className="item-header">Last Name</div>
                      {editView ? (
                        <TextInput
                          placeholder={user?.last_name}
                          type="text"
                          aria-label="last name"
                          className="editInput"
                          name="last_name"
                          value={user?.last_name}
                          onChange={(val) =>
                            handleInputChange(val, "last_name")
                          }
                        />
                      ) : (
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
                      {editView ? (
                        <TextInput
                          value={user?.username}
                          type="text"
                          isReadOnly
                          aria-label="user name"
                          className="editInput"
                        />
                      ) : (
                        <TextContent>
                          <Text component={TextVariants.h5}>
                            {user?.username}
                          </Text>
                        </TextContent>
                      )}
                    </GridItem>
                    <GridItem md={6} lg={4} className="item-container">
                      <div className="item-header">Email</div>
                      {editView ? (
                        <TextInput
                          placeholder={user?.email}
                          type="text"
                          aria-label="email"
                          className="editInput"
                          name="email"
                          value={user?.email}
                          onChange={(val) => handleInputChange(val, "email")}
                        />
                      ) : (
                        <TextContent>
                          <Text component={TextVariants.h5}>{user?.email}</Text>
                        </TextContent>
                      )}
                    </GridItem>
                  </Grid>
                  {editView ? (
                    <Grid span={12} className="grid">
                      <GridItem className="grid">
                        <Button
                          variant="primary"
                          className="profileBtn"
                          onClick={saveEdit}
                          isDisabled={!isUserDetailsUpdated}
                        >
                          Save
                        </Button>{" "}
                        <Button
                          variant="secondary"
                          className="profileBtn"
                          onClick={edit}
                        >
                          Cancel
                        </Button>
                      </GridItem>
                    </Grid>
                  ) : (
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
