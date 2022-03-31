import {toast} from "react-toastify";

function wrongCredentials(bounce) {
    toast.error("Invalid username/password,try again!!", {
        transition: bounce
      });
}

export default wrongCredentials