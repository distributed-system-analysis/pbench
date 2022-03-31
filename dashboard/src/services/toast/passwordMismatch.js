import {toast} from "react-toastify";

function passwordMismatch(bounce) {
    toast.error("Password do not match", {
        transition: bounce
      });
}

export default passwordMismatch