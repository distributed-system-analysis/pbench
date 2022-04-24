export const filterData = (dataArray, startDate, endDate, controllerValue) => {
  let res = dataArray.filter((data) => {
    return (
      data.controller.includes(controllerValue) &&
      new Date(data.metadata["dataset.created"].split(":")[0]) >= startDate &&
      new Date(data.metadata["dataset.created"].split(":")[0]) <= new Date(endDate)
    );
  });
  return res;
};
