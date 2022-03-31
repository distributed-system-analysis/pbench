import {toast} from "react-toastify";
function wrongPasswordEmail(bounce) {
    toast.error("Please enter valid email/password", {
        transition: bounce
      });
}

export default wrongPasswordEmail