/**
 * Bump the supplied date ahead by specified number of days
 * @function
 * @param {Date} date - Date to be bumped
 * @param {number} numberOfDays - Number of days the date is to be bumped
 * @returns {Date} - New Bumped date
 */
export const bumpToDate = (date, numberOfDays) => {
  return date.setUTCDate(date.getUTCDate() + numberOfDays);
};

/**
 * Convert a date string into UTC Date object
 * Date should not contain timezone related information,else + "Z" will result in an error
 * @function
 * @param {string} strDate - Date in string format
 * @returns {Date} - UTC Date object
 */
export const dateFromUTCString = (strDate) => {
  return new Date(strDate + "Z");
};

/**
 * Return a Date object representing the current day, UTC, with the time set to midnight
 * @function
 * @returns {Date} - current UTC Date with the time set to Midnight
 */
export const getTodayMidnightUTCDate = () => {
  const midnightUTC = new Date();
  midnightUTC.setUTCHours(0, 0, 0, 0);
  return midnightUTC;
};
