import request from '../utils/request';

export default async function querySharedSessions(params) {
  const { datastoreConfig } = params;

  const endpoint = `${datastoreConfig.graphql}`;

  return request.post(endpoint, {
    data: {
      query: `
        query {
          urls {
              id
              config
              description
              createdAt
          }   
        }`,
    },
  });
}
