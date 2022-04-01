/**
 * Bump the supplied date ahead by specified number of days
 * @function
 * @param {Date} date - Date to be bumped
 * @param {number} numberOfDays - Number of days the date is to be bumped
 * @return {Date} - New Bumped date
 */
export const bumpToDate = (date, numberOfDays) => {
  return date.setUTCDate(date.getUTCDate() + numberOfDays);
};

/**
 * Convert a date string into UTC Date object
 * Date should not contain timezone related information,else + "Z" will result in an error
 * @function
 * @param {string} strDate - Date in string format
 * @return {Date} - UTC Date object
 */
export const dateFromUTCString = (strDate) => {
  return new Date(strDate + "Z");
};

/**
 * Return a Date object representing the current day, UTC, with the time set to midnight
 * @function
 * @return {Date} - current UTC Date with the time set to Midnight
 */
export const getTodayMidnightUTCDate = () => {
  const midnightUTC = new Date();
  midnightUTC.setUTCHours(0, 0, 0, 0);
  return midnightUTC;
};

/**
 * Convert a date string into Locale Date String with seconds and milli seconds removed *
 * @function
 * @param {string} strDate - Date in string format
 * @return {string} - Locale Date string
 */

export const formatDateTime = (dateTimeStamp) => {
  const dateObj = new Date(dateTimeStamp);
  dateObj.setSeconds(0, 0);
  return dateObj.toLocaleString();
};
/**
 * Find number of days between given date and today's date*
 * @function
 * @param {string} dateString - Date in string format
 * @return {number} - Number of days in number format
 */
export const findNoOfDays = (dateString) => {
  const deletionDate = new Date(dateString);
  const today = new Date();
  const diffTime = Math.abs(deletionDate - today);
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
};
