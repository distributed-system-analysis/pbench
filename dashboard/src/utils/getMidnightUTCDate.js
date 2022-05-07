export const getMidnightUTCDate = () => {
  const midnightUTC = new Date();
  midnightUTC.setUTCHours(0);
  midnightUTC.setUTCMinutes(0);
  midnightUTC.setUTCSeconds(0);
  midnightUTC.setUTCMilliseconds(0);
  return midnightUTC;
};
