import request from '../utils/request';

export async function querySharedSessions(params) {
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

export async function queryEditDescription(params) {
  const { datastoreConfig, id, value } = params;

  const endpoint = `${datastoreConfig.graphql}`;

  return request.post(endpoint, {
    data: {
      query: `
        mutation($description: String!,$id: ID!) {
        updateUrl(
          data: {description: $description}
          where: {id: $id})
        {
          id
          config
          description
        }
      }`,
      variables: {
        id,
        description: value,
      },
    },
  });
}
