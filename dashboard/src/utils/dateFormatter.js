export const formatDate = (date) => {
  const utcdateMonth =
    date.getUTCMonth() + 1 < 10
      ? `0${date.getUTCMonth() + 1}`
      : date.getUTCMonth() + 1;
  const utcDate =
    date.getUTCDate() < 10 ? `0${date.getUTCDate()}` : date.getUTCDate();
  return `${date.getUTCFullYear()}-${utcdateMonth}-${utcDate}`;
};
