import * as types from "./types";
import API from "../utils/api";

export const makeLoginRequest = (details) => async(dispatch, getState) => {
    try {
        dispatch({type: types.LOADING});
        let toast = {};
        const response = await API.post('api/v1/login', {
            username: details.username,
            password: details.password
        });
        if(response.status === 200) {
            toast = {
                variant: 'info',
                title: 'Logged in'
            }
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