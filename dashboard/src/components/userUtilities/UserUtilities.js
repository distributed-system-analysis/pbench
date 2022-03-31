import React, { useEffect, useState } from 'react'
import logout from '../../assets/logout.png'
import axios from 'axios'
import { useNavigate } from 'react-router-dom'
import { Modal, ModalVariant, Button, Form, FormGroup, Popover, TextInput } from '@patternfly/react-core';
import HelpIcon from '@patternfly/react-icons/dist/esm/icons/help-icon';
import panda from '../../assets/panda.jpeg'
import './userUtilities.css'
import { ToastContainer, cssTransition } from "react-toastify";
import moment from 'moment'
import updateSuccess from '../../services/toast/updateSuccess';
import editFailed from '../../services/toast/editFailed';
const bounce = cssTransition({
  enter: "animate__animated animate__bounceIn",
  exit: "animate__animated animate__bounceOut"
});
function UserUtilities({ accountName, isUserLogin }) {
  const navigate = useNavigate()
  const [userData, setUserData] = useState({})
  const [isModalOpen, setModalOpen] = useState(false);
  const [firstNameValue, setFirstNameValue] = useState('');
  const [lastNameValue, setLastNameValue] = useState('');
  const token = localStorage.getItem('token') ? localStorage.getItem('token') : ''
  const user = localStorage.getItem('user') ? localStorage.getItem('user') : ''
  useEffect(() => {
    axios.get(`${process.env.REACT_APP_USER}/${user}`,
      {
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          "Authorization": `Bearer ${token}`
        }
      }).then(res => {
        setUserData(res.data)
        setFirstNameValue(res.data.first_name)
        setLastNameValue(res.data.last_name)
      })
      .catch(err => {
        console.log(err);
      })
  }, [])

  const handleModalToggle = () => {
    setModalOpen(!isModalOpen);
  };
  const handleFirstNameInputChange = value => {
    setFirstNameValue(value);
  };
  const handleLastNameInputChange = value => {
    setLastNameValue(value);
  };

  const changeProfileHandler = () => {
    if ((userData.first_name !== firstNameValue || userData.last_name !== lastNameValue) && firstNameValue !== "" && lastNameValue !== "") {
      axios.put(`${process.env.REACT_APP_USER}/${user}`, {
        first_name: firstNameValue,
        last_name: lastNameValue,
      },
        {
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            "Authorization": `Bearer ${token}`
          }
        }).then((res) => {
          setUserData(res.data)
          handleModalToggle()
          updateSuccess(bounce)
        })
        .catch(err => console.log(err.message))
    }
    else if (firstNameValue === "")
      editFailed("First Name field cannot be blank", bounce)
    else if (lastNameValue === "")
      editFailed("Last Name field cannot be blank", bounce)
    else if (userData.first_name === firstNameValue && userData.last_name === lastNameValue)
      editFailed("Please Provide new values", bounce)
    else
      console.log("error");
  }
  const handleLogout = () => {
    axios.post(`${process.env.REACT_APP_LOGOUT}`, {},
      {
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          "Authorization": `Bearer ${token}`
        }
      }
    ).then(res => {

      localStorage.clear();
      navigate('/')

    }).catch(err => {

      console.log(err);
    })
  }
  const toggleVisibility = () => {
    const userProfile = document.querySelector('.profileContainer')
    userProfile.classList.toggle('active')
  }
  const editModalToggle = () => {
    handleModalToggle()
    toggleVisibility()
  }
  const goToLogin = () => {
    navigate('/')
  }
  return (
    <>
      {isUserLogin ? (<img src={logout} className='logout-icon' onClick={handleLogout}></img>)
        :
        <span style={{ 'cursor': 'pointer', 'fontWeight': 'bold', 'marginRight': '25px', 'fontSize': '18px' }} onClick={goToLogin}>LogIn</span>}
      {isUserLogin ? (<img src={panda} className='profile-pic' height="36px" width="36px" alt='profile pic' onClick={toggleVisibility}></img>) : ''}
      <div className='profileContainer'>
        <div className='userInfo'>
          <img src={panda} className='profile-pic' height="36px" width="36px" alt='profile pic' onClick={toggleVisibility}></img>
        </div>
        <div className='userInfo'>
          <span>{accountName === undefined ? `${userData.first_name} ${userData.last_name}` : accountName}</span>
        </div>
        <div className='userInfo'>
          <span>~{userData.username}</span>
        </div>
        <hr></hr>
        <div className='userInfo'>
          <span>Member since {moment(userData.registered_on).format("MMM Do YY")}</span>
        </div>
        <div className='userInfo'>
          <button onClick={editModalToggle}>Edit Profile</button>
        </div>
        <ToastContainer transition={bounce} position='top-center' hideProgressBar={true} autoClose={3000} />
      </div>
      <Modal variant={ModalVariant.small} title="Edit Profile" description="Edit your Profile by changing the fields below" isOpen={isModalOpen} onClose={handleModalToggle} actions={[<Button key="create" variant="primary" form="modal-with-form-form" onClick={changeProfileHandler}>
        Confirm
      </Button>, <Button key="cancel" variant="link" onClick={handleModalToggle}>
        Cancel
      </Button>]}>
        <Form id="modal-with-form-form">
          <FormGroup label="First Name" labelIcon={<Popover headerContent={<div>
            What is a First Name?

          </div>} bodyContent={<div>
            The first name of a person is often his given Name.
          </div>}>
            <button type="button" aria-label="More info for name field" onClick={e => e.preventDefault()} aria-describedby="modal-with-form-form-name" className="pf-c-form__group-label-help">
              <HelpIcon noVerticalAlign />
            </button>
          </Popover>} isRequired fieldId="modal-with-form-form-name">
            <TextInput isRequired type="email" id="modal-with-form-form-name" name="modal-with-form-form-name" value={firstNameValue} onChange={handleFirstNameInputChange} className={firstNameValue === "" ? "invalid" : ""} />
          </FormGroup>
          <FormGroup label="Last Name" labelIcon={<Popover headerContent={<div>
            What is a Last Name?

          </div>} bodyContent={<div>
            The Last Name of a Person is often his family Name.
          </div>}>
            <button type="button" aria-label="More info for e-mail field" onClick={e => e.preventDefault()} aria-describedby="modal-with-form-form-email" className="pf-c-form__group-label-help">
              <HelpIcon noVerticalAlign />
            </button>
          </Popover>} isRequired fieldId="modal-with-form-form-email">
            <TextInput isRequired type="email" id="modal-with-form-form-email" name="modal-with-form-form-email" value={lastNameValue} onChange={handleLastNameInputChange} className={lastNameValue === "" ? "invalid" : ""} />
          </FormGroup>
        </Form>
      </Modal>
    </>
  )
}

export default UserUtilities