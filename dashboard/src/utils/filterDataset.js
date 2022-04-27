import { constructNewDate } from "./constructDate";

export const filterData = (dataArray, startDate, endDate, controllerValue) => {
  let res = dataArray.filter((data) => {
    let datasetDate = constructNewDate(data.metadata["dataset.created"]);
    return (
      data.controller.includes(controllerValue) &&
      datasetDate >= startDate &&
      datasetDate <= endDate
    );
  });
  return res;
};
