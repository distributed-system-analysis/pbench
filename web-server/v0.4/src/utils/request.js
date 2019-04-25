import { extend } from 'umi-request';
import { notification } from 'antd';
import router from 'umi/router';

const codeMessage = {
  200: 'The server successfully returned the requested data. ',
  201: 'New or modified data is successful. ',
  202: 'A request has entered the background queue (asynchronous task). ',
  204: 'The data was deleted successfully. ',
  400: 'The request returned an error and the server did not perform any new or modified data operations. ',
  401: 'User does not have permission (token, username, or password is incorrect). ',
  403: 'The user is authorized, but access is forbidden. ',
  404: 'The request was made for a record that does not exist. ',
  406: 'The format of the request is not available. ',
  410: 'The requested resource is permanently deleted and will not be retrieved. ',
  422: 'A validation error occurred when creating an object. ',
  500: 'An error occurred on the server. Please check the server. ',
  502: 'Gateway error. ',
  503: 'The service is unavailable and the server is temporarily overloaded or maintained. ',
  504: 'The gateway timed out. ',
};

const errorHandler = error => {
  const { response = {} } = error;
  const errortext = codeMessage[response.status] || response.statusText;
  const { status, url } = response;

  notification.error({
    message: `Request Error ${status}: ${url}`,
    description: errortext,
  });

  if (status === 403) {
    router.push('/exception/403');
    return;
  }
  if (status === 404) {
    router.goBack();
    return;
  }
  if (status <= 504 && status >= 500) {
    router.push('/exception/500');
    return;
  }
  if (status >= 405 && status < 422) {
    router.push('/exception/404');
  }
};

const request = extend({
  errorHandler, // extend default error handler with custom actions
});

export default request;
