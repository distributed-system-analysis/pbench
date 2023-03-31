export const uid = () => {
  const head = Date.now().toString(36);
  const tail = Math.random().toString(36).substring(2);

  return head + tail;
};

/**
 * Expand a templated API URI like a Python `.format`
 *
 * @param {Object} endpoints - endpoint object from server
 * @param {string} name - name of the API to expand
 * @param {Object} args - [Optional] value for each templated parameter
 * @return {string} - formatted URI
 */
export const uriTemplate = (endpoints, name, args = {}) => {
  let uri = endpoints.uri[name].template;
  for (const [key, value] of Object.entries(args)) {
    uri = uri.replace(`{${key}}`, value);
  }
  return uri;
};
