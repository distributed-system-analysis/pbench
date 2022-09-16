import * as TYPES from "./types";

export const fetchEndpoints = async (dispatch) => {
  try {
    const response = await fetch("/api/v1/endpoints");

    if (!response.ok) {
      throw new Error(`Network error! status: ${response.status}`);
    }
    const data = await response.json();
    dispatch({
      type: TYPES.SET_ENDPOINTS,
      payload: data,
    });
  } catch (error) {
    dispatch({
      type: TYPES.SHOW_TOAST,
      payload: {
        variant: "danger",
        title: `Something went wrong, ${error}`,
      },
    });
  }
};
