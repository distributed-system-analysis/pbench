export const formatDate = (date) => {
  return `${date.getFullYear()}-0${date.getMonth() + 1}-${date.getDate()}`;
};
