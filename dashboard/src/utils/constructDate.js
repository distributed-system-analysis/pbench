export const constructUTCDate = (date) => {
  return date.setMinutes(date.getMinutes()+date.getTimezoneOffset());
};
