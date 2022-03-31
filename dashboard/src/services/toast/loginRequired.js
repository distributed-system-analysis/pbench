import {toast} from "react-toastify";

function loginRequired(bounce) {
    toast.warn("You have to login to perform this action", {
        transition: bounce
      });
}
export default loginRequired