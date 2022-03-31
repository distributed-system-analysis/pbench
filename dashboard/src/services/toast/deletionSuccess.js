import {toast} from "react-toastify";

function deletionSuccess(bounce) {
    toast.success("Successfully deleted Datasets!!", {
        transition: bounce
      });
}

export default deletionSuccess