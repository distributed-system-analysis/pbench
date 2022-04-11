import * as types from "./types";
import API from "../utils/api";
import Cookies from 'js-cookie';

export const makeLoginRequest = (details) => async(dispatch, getState) => {
    try {
        dispatch({type: types.LOADING});
        let toast = {};
        const response = await API.post('api/v1/login', {
            ...details
        });
        if(response.status === 200 && Object.keys(response.data).length > 0) {
            let keepUser = getState().userAuth.keepLoggedIn;
            let expiryTime = keepUser ? 7 : 0.5;
            Cookies.set('isLoggedIn', true, { expires: expiryTime});
            Cookies.set('token', response.data?.auth_token, { expires: expiryTime });
            Cookies.set('username', response.data?.username, { expires: expiryTime });
        } else {
            toast= {
                variant: 'danger',
                title: 'Invalid Crendtials'
            }
        }
        dispatch({
            type: types.SHOW_TOAST, 
            payload: {...toast}
        })
        dispatch({type: types.COMPLETED})
    } catch{
        dispatch({type: types.NETWORK_ERROR})
        dispatch({type: types.COMPLETED})
    }
    
}

export const movePage = (toPage, navigate) => async() => {
    navigate(toPage);
}

export const setUserLoggedInState = (value) => async(dispatch) => {
    dispatch({
        type: types.KEEP_USER_LOGGED_IN,
        payload: value
    })
}

export const registerUser = (details) => async(dispatch) => {
    try {
        dispatch({type: types.LOADING});
        let toast = {};
        const response = await API.post('api/v1/register', {
            ...details
        });
        if(response.status === 200 && Object.keys(response.data).length > 0) {
            console.log("hi");
        } else {
            toast= {
                variant: 'danger',
                title: 'Invalid Crendtials'
            }
        }
        dispatch({
            type: types.SHOW_TOAST, 
            payload: {...toast}
        })
        dispatch({type: types.COMPLETED})
    } catch{
        dispatch({type: types.NETWORK_ERROR})
        dispatch({type: types.COMPLETED})
    }
    
}