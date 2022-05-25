/**
 * Bump Todate ahead by specified number of days
 * @function
 * @param {Date} date - Date to be bumped
 * @param {number} numberOfDays - Number of days the date is to be bumped
 * @returns {Date} - New Bumped date
 */
export const bumpToDate = (date, numberOfDays) => {
  return date.setUTCDate(date.getUTCDate() + numberOfDays);
};

/**
 * Takes a string date and convert it into UTC Date object
 * @function
 * @param {string} strDate - Date in string format
 * @returns {Date} - UTC Date object
 */
export const dateFromUTCString = (strDate) => {
  return new Date(strDate + "Z");
};

/**
 * Set today's date to Midnight UTC
 * @function
 * @returns {Date} - UTC Date set to Midnight
 */
export const getTodayMidnightUTCDate = () => {
  const midnightUTC = new Date();
  midnightUTC.setUTCHours(0, 0, 0, 0);
  return midnightUTC;
};
