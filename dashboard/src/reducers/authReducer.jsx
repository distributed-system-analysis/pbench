import { KEEP_USER_LOGGED_IN } from "../actions/types";

const initialState = {
    keepLoggedIn : false
}

const AuthReducer = (state = initialState, action = {}) => {
    const { type, payload } = action;
    switch (type) {
        case KEEP_USER_LOGGED_IN:
            return {
                ...state,
                keepLoggedIn: payload
            }
        default:
            return state;
    }
}

export default AuthReducer;