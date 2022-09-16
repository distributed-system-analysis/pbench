/**
 * Filter the List of Datasets based on Date Range and Dataset Name
 * @function
 * @param {Array} dataArray - Array of Datasets
 * @param {Date} startDate - Start Date selected from Date Picker
 * @param {Date} endDate - End Date selected from Date Picker
 * @param {string} searchKey - Dataset Name entered in the search box
 * @return {Array} - Array of filtered Datasets
 */
export const filterData = (dataArray, startDate, endDate, searchKey) => {
  return dataArray.filter((data) => {
    const datasetDate = new Date(data.metadata[DATASET_CREATED]);
    return (
      data.name.includes(searchKey) &&
      datasetDate >= startDate &&
      datasetDate <= endDate
    );
  });
};
