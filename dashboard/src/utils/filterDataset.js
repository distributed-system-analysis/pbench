/**
 * Filter the Dataset based on Date Range or Dataset Name or both
 * @function
 * @param {Array} dataArray - Array of Datasets
 * @param {Date} startDate - Start Date selected from Date Picker
 * @param {Date} endDate - End Date selected from Date Picker
 * @param {string} searchKey - Dataset Name entered in the search box
 * @returns {Array} - Array of filtered Datasets
 */
export const filterData = (dataArray, startDate, endDate, searchKey) => {
  return dataArray.filter((data) => {
    let datasetDate = new Date(data.metadata["dataset.created"]);
    return (
      data.name.includes(searchKey) &&
      datasetDate >= startDate &&
      datasetDate <= endDate
    );
  });
};
