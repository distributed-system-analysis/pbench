import {toast} from "react-toastify";

function userExist(bounce) {
    toast.error("User already exist", {
        transition: bounce
      });
}

export default userExist